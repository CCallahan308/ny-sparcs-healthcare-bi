"""Mart build, grain, row-count, reconciliation, and validation tests."""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest
from src.config import MART_EXPORTS
from src.quality import validate_marts
from src.transform import SQL_MARTS_DIR, execute_sql_dir, export_marts, run_transformations

EXPECTED_YEARS = {2009, 2011, 2024}
EXPECTED_TOTAL_DISCHARGES = 12  # 4 rows per fixture year, including 1 redacted


@pytest.fixture()
def marts_dir(pipeline_conn: duckdb.DuckDBPyConnection, tmp_path):
    run_transformations(pipeline_conn, tmp_path)
    return tmp_path


def _read(conn: duckdb.DuckDBPyConnection, path, sql: str):
    return conn.execute(sql.format(path=path.as_posix())).fetchall()


def test_all_marts_exported_nonempty(marts_dir, pipeline_conn) -> None:
    for file_name in MART_EXPORTS.values():
        path = marts_dir / file_name
        assert path.exists() and path.stat().st_size > 0, file_name
        rows = pipeline_conn.execute(
            f"SELECT COUNT(*) FROM read_parquet('{path.as_posix()}')"
        ).fetchone()[0]
        assert rows > 0, file_name


def test_year_coverage_matches_staging(marts_dir, pipeline_conn) -> None:
    for file_name in MART_EXPORTS.values():
        path = marts_dir / file_name
        column_names = {
            row[0]
            for row in pipeline_conn.execute(
                f"DESCRIBE SELECT * FROM read_parquet('{path.as_posix()}')"
            ).fetchall()
        }
        if "discharge_year" not in column_names:
            continue
        years = {
            row[0]
            for row in pipeline_conn.execute(
                f"SELECT DISTINCT discharge_year FROM read_parquet('{path.as_posix()}')"
            ).fetchall()
        }
        assert years == EXPECTED_YEARS, file_name


def test_reconciliation_trends_match_staging(
    marts_dir, pipeline_conn: duckdb.DuckDBPyConnection
) -> None:
    path = marts_dir / "executive_trends.parquet"
    totals = _read(
        pipeline_conn,
        path,
        "SELECT SUM(discharges), SUM(estimated_cost) FROM read_parquet('{path}')",
    )[0]
    staging = pipeline_conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(total_costs), 0) FROM stg_normalized"
    ).fetchone()
    assert totals[0] == staging[0] == EXPECTED_TOTAL_DISCHARGES
    assert totals[1] == pytest.approx(staging[1])


def test_trend_derived_metrics_match_metrics_module(
    marts_dir, pipeline_conn: duckdb.DuckDBPyConnection
) -> None:
    from src import metrics

    path = marts_dir / "executive_trends.parquet"
    row = pipeline_conn.execute(
        f"SELECT * FROM read_parquet('{path.as_posix()}') WHERE discharge_year = 2024"
    ).fetchone()
    (
        discharges,
        cost,
        los_days,
        high_sev,
        ed,
        post_acute,
        cpd,
        cpday,
        alos,
        sev_share,
        ed_rate,
        pa_rate,
    ) = (
        row[1],
        row[2],
        row[4],
        row[5],
        row[6],
        row[7],
        row[8],
        row[9],
        row[10],
        row[11],
        row[12],
        row[13],
    )
    assert cpd == pytest.approx(metrics.cost_per_discharge(cost, discharges))
    assert cpday == pytest.approx(metrics.cost_per_day(cost, los_days))
    assert alos == pytest.approx(metrics.alos(los_days, discharges))
    assert sev_share == pytest.approx(metrics.high_severity_share(high_sev, discharges))
    assert ed_rate == pytest.approx(metrics.ed_origin_rate(ed, discharges))
    assert pa_rate == pytest.approx(metrics.post_acute_rate(post_acute, discharges))


def test_zero_denominator_yields_null_not_error(
    pipeline_conn: duckdb.DuckDBPyConnection, tmp_path
) -> None:
    pipeline_conn.execute(
        """
        INSERT INTO stg_normalized
        (source_year, discharge_year, facility_id, facility_name, county,
         facility_redacted, mdc_code, mdc_description, apr_drg_code,
         apr_drg_description, severity_code, high_severity, los_days,
         los_capped, ed_origin, admission_type, disposition_raw, post_acute,
         payer_raw, payer_class, total_charges, total_costs, clinical_grouping)
        VALUES (2030, 2030, 'X1', 'Zero LOS Facility', 'Democounty', false,
                '05', 'Circulatory', '302', 'Zero LOS DRG', 1, false, 0,
                false, false, 'Elective', 'Home or Self Care', false,
                'Medicaid', 'Medicaid', 500.0, 400.0, 'CCS')
        """
    )
    # Rebuild marts only; rerunning staging would wipe the synthetic row.
    execute_sql_dir(pipeline_conn, SQL_MARTS_DIR)
    export_marts(pipeline_conn, tmp_path)
    row = pipeline_conn.execute(
        f"SELECT discharges, cost_per_discharge, cost_per_day, alos "
        f"FROM read_parquet('{(tmp_path / 'executive_trends.parquet').as_posix()}') "
        "WHERE discharge_year = 2030"
    ).fetchone()
    assert row == (1, 400.0, None, 0.0)


def test_facility_benchmarks_excludes_redacted(
    marts_dir, pipeline_conn: duckdb.DuckDBPyConnection
) -> None:
    path = marts_dir / "facility_benchmarks.parquet"
    redacted_in_benchmarks = pipeline_conn.execute(
        f"SELECT COUNT(*) FROM read_parquet('{path.as_posix()}') "
        "WHERE facility_id IS NULL OR TRIM(facility_id) = ''"
    ).fetchone()[0]
    assert redacted_in_benchmarks == 0
    facilities_2009 = pipeline_conn.execute(
        f"SELECT COUNT(*) FROM read_parquet('{path.as_posix()}') WHERE discharge_year = 2009"
    ).fetchone()[0]
    assert facilities_2009 == 2  # redacted row excluded


def test_payer_exposure_totals_reconcile(
    marts_dir, pipeline_conn: duckdb.DuckDBPyConnection
) -> None:
    path = marts_dir / "payer_exposure.parquet"
    total = pipeline_conn.execute(
        f"SELECT SUM(discharges) FROM read_parquet('{path.as_posix()}')"
    ).fetchone()[0]
    assert total == EXPECTED_TOTAL_DISCHARGES
    classes = {
        row[0]
        for row in pipeline_conn.execute(
            f"SELECT DISTINCT payer_class FROM read_parquet('{path.as_posix()}')"
        ).fetchall()
    }
    assert classes <= {
        "Medicare",
        "Medicaid",
        "Private",
        "Managed Care",
        "Self-Pay",
        "Other Government",
        "Other",
        "Unknown",
    }


def test_process_control_series_shapes(marts_dir, pipeline_conn) -> None:
    path = marts_dir / "process_control_series.parquet"
    statewide_metrics = {
        row[0]
        for row in pipeline_conn.execute(
            f"SELECT DISTINCT metric FROM read_parquet('{path.as_posix()}') "
            "WHERE series_id = 'statewide'"
        ).fetchall()
    }
    assert statewide_metrics == {
        "alos",
        "cost_per_discharge",
        "post_acute_rate",
        "high_severity_share",
        "ed_origin_rate",
    }
    alos_2024 = pipeline_conn.execute(
        f"SELECT value FROM read_parquet('{path.as_posix()}') "
        "WHERE metric = 'alos' AND series_id = 'statewide' AND discharge_year = 2024"
    ).fetchone()[0]
    trend_alos = pipeline_conn.execute(
        "SELECT alos FROM mart_executive_trends WHERE discharge_year = 2024"
    ).fetchone()[0]
    assert alos_2024 == pytest.approx(trend_alos)


def test_data_quality_summary_flags_redaction(marts_dir, pipeline_conn) -> None:
    path = marts_dir / "data_quality_summary.parquet"
    row = pipeline_conn.execute(
        f"SELECT rows, facility_redacted_share, negative_costs, los_capped "
        f"FROM read_parquet('{path.as_posix()}') WHERE year = 2009"
    ).fetchone()
    assert row[0] == 4
    assert row[1] == pytest.approx(0.25)
    assert row[2] == 0
    assert row[3] == 1


def test_validator_flags_negative_measures(
    marts_dir, pipeline_conn: duckdb.DuckDBPyConnection
) -> None:
    path = marts_dir / "payer_exposure.parquet"
    frame = pd.read_parquet(path)
    frame.loc[0, "estimated_cost"] = -5.0
    frame.to_parquet(path)
    issues = validate_marts(pipeline_conn, marts_dir)
    assert any("negative" in issue and "estimated_cost" in issue for issue in issues)


def test_validator_passes_on_clean_build(
    marts_dir, pipeline_conn: duckdb.DuckDBPyConnection
) -> None:
    assert validate_marts(pipeline_conn, marts_dir) == []
