"""Staging normalization tests: payer, disposition, severity, flags."""

from __future__ import annotations

import duckdb


def _fetch(conn: duckdb.DuckDBPyConnection, sql: str, params: list | None = None):
    return conn.execute(sql, params or []).fetchall()


def test_payer_harmonization_across_eras(pipeline_conn: duckdb.DuckDBPyConnection) -> None:
    rows = _fetch(
        pipeline_conn,
        "SELECT DISTINCT payer_raw, payer_class FROM stg_normalized ORDER BY payer_raw",
    )
    mapping = dict(rows)
    assert mapping["Insurance Company"] == "Private"
    assert mapping["Blue Cross"] == "Private"
    assert mapping["Blue Cross/Blue Shield"] == "Private"
    assert mapping["Private Health Insurance"] == "Private"
    assert mapping["Medicare"] == "Medicare"
    assert mapping["Medicaid"] == "Medicaid"
    assert mapping["Self-Pay"] == "Self-Pay"
    assert mapping["Other Non-Federal Program"] == "Other"


def test_blank_payer_becomes_unknown(pipeline_conn: duckdb.DuckDBPyConnection) -> None:
    unknown_blank = _fetch(
        pipeline_conn,
        "SELECT COUNT(*) FROM stg_normalized "
        "WHERE TRIM(COALESCE(payer_raw, '')) = '' AND payer_class = 'Unknown'",
    )[0][0]
    assert unknown_blank > 0


def test_post_acute_disposition_mapping(pipeline_conn: duckdb.DuckDBPyConnection) -> None:
    rows = _fetch(
        pipeline_conn,
        "SELECT DISTINCT disposition_raw, post_acute FROM stg_normalized ORDER BY disposition_raw",
    )
    post_acute = dict(rows)
    assert post_acute["Skilled Nursing Home"] is True
    assert post_acute["Hospice - Medical Facility"] is True
    assert post_acute["Home or Self Care"] is False
    assert post_acute["Another Type of Health Care Facility"] is False


def test_severity_parsing_and_high_severity_flag(
    pipeline_conn: duckdb.DuckDBPyConnection,
) -> None:
    # 2011 carries codes in the plain column; 2024 resolves the code column
    # and must not pick up the word-form description column.
    severity_2011 = _fetch(
        pipeline_conn,
        "SELECT severity_code FROM stg_normalized WHERE source_year = 2011 AND los_capped",
    )[0][0]
    assert severity_2011 == 4
    severity_2024 = _fetch(
        pipeline_conn,
        "SELECT severity_code FROM stg_normalized WHERE source_year = 2024 "
        "AND apr_drg_code = '302'",
    )[0][0]
    assert severity_2024 == 2
    high_share = _fetch(
        pipeline_conn,
        "SELECT COUNT(*) FILTER (WHERE severity_code >= 3), "
        "COUNT(*) FILTER (WHERE high_severity) FROM stg_normalized",
    )[0]
    assert high_share[0] == high_share[1]
    severity_zero_not_high = _fetch(
        pipeline_conn,
        "SELECT COUNT(*) FROM stg_normalized WHERE severity_code = 0 AND high_severity",
    )[0][0]
    assert severity_zero_not_high == 0


def test_ed_origin_and_los_capped_flags(
    pipeline_conn: duckdb.DuckDBPyConnection,
) -> None:
    counts = _fetch(
        pipeline_conn,
        "SELECT COUNT(*) FILTER (WHERE ed_origin), "
        "COUNT(*) FILTER (WHERE los_capped), "
        "COUNT(*) FILTER (WHERE los_days = 120 AND los_capped) FROM stg_normalized",
    )[0]
    assert counts[0] > 0
    assert counts[1] == 3
    assert counts[1] == counts[2]


def test_redacted_facility_flag(pipeline_conn: duckdb.DuckDBPyConnection) -> None:
    redacted = _fetch(
        pipeline_conn,
        "SELECT COUNT(*) FROM stg_normalized WHERE facility_redacted",
    )[0][0]
    assert redacted == 1


def test_clinical_grouping_family(pipeline_conn: duckdb.DuckDBPyConnection) -> None:
    families = _fetch(
        pipeline_conn,
        "SELECT source_year, clinical_grouping FROM stg_normalized GROUP BY 1, 2 ORDER BY 1",
    )
    assert families == [(2009, "CCS"), (2011, "CCS"), (2024, "CCSR")]


def test_service_line_key_uses_mdc(pipeline_conn: duckdb.DuckDBPyConnection) -> None:
    rows = _fetch(
        pipeline_conn,
        "SELECT DISTINCT mdc_code, mdc_description FROM stg_normalized WHERE mdc_code IS NOT NULL",
    )
    assert len(rows) > 0
    assert all(code and label for code, label in rows)


def test_no_negative_measures_in_normalized_staging(
    pipeline_conn: duckdb.DuckDBPyConnection,
) -> None:
    negatives = _fetch(
        pipeline_conn,
        "SELECT COUNT(*) FROM stg_normalized WHERE total_costs < 0 "
        "OR total_charges < 0 OR los_days < 0",
    )[0][0]
    assert negatives == 0


def test_normalized_row_count_matches_staging(
    pipeline_conn: duckdb.DuckDBPyConnection,
) -> None:
    counts = _fetch(
        pipeline_conn,
        "SELECT (SELECT COUNT(*) FROM stg_discharges), (SELECT COUNT(*) FROM stg_normalized)",
    )[0]
    assert counts[0] == counts[1]


def test_drg_description_drift_gets_one_canonical_label(
    tmp_path,
    monkeypatch,  # noqa: ANN001
) -> None:
    """A reworded DRG keeps one code, one label: the latest year's wording."""
    from src import ingest
    from src.transform import SQL_STAGING_DIR, execute_sql_dir
    from tests.conftest import FIXTURE_YEARS, FIXTURES

    # Simulate a NY DOH reword: 2024 renames code 194, and one 2024 row
    # loses its description entirely (must inherit the canonical label).
    drifted = (
        (FIXTURES / "sparcs_2024_style.csv")
        .read_text(encoding="utf-8")
        .replace("Cardiac arrhythmia w CC", "Cardiac Arrhythmia with CC")
        .replace("Cardiac ablation w/o MCC", "", 1)
    )
    drifted_path = tmp_path / "sparcs_2024_drifted.csv"
    drifted_path.write_text(drifted, encoding="utf-8")

    conn = duckdb.connect()
    try:
        ingest.ensure_staging(conn)
        for name, year in FIXTURE_YEARS.items():
            source = drifted_path if year == 2024 else FIXTURES / name
            ingest.ingest_file(conn, source, year)
        execute_sql_dir(conn, SQL_STAGING_DIR)

        drifted_codes = conn.execute(
            """
            SELECT apr_drg_code, COUNT(DISTINCT apr_drg_description) AS variants
            FROM stg_normalized
            WHERE apr_drg_code IS NOT NULL
            GROUP BY apr_drg_code
            HAVING COUNT(DISTINCT apr_drg_description) > 1
            """
        ).fetchall()
        assert drifted_codes == [], f"codes with conflicting labels: {drifted_codes}"

        code_194 = conn.execute(
            """
            SELECT DISTINCT apr_drg_description, discharge_year
            FROM stg_normalized WHERE apr_drg_code = '194'
            ORDER BY discharge_year
            """
        ).fetchall()
        assert {label for label, _ in code_194} == {"Cardiac Arrhythmia with CC"}, code_194

        blank_desc = conn.execute(
            """
            SELECT COUNT(*) FROM stg_normalized
            WHERE apr_drg_code IS NOT NULL AND TRIM(apr_drg_description) = ''
            """
        ).fetchone()[0]
        assert blank_desc == 0, "blank descriptions should inherit the canonical label"
    finally:
        conn.close()
