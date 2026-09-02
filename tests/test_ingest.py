"""Ingestion and canonical field-mapping tests.

Fixtures are synthetic and represent the schema variants verified in the real
annual files (see docs/schema_drift.md): display vs API header styles, the
Source-of-Payment to Payment-Typology rename, the 2011 deviations, and
dollar-formatted money.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import duckdb
import pytest
from src import download, ingest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_headers(name: str) -> list[str]:
    with open(FIXTURES / name, encoding="utf-8") as handle:
        return next(csv.reader(handle))


@pytest.fixture()
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    ingest.ensure_staging(connection)
    yield connection
    connection.close()


def test_display_case_headers_resolve() -> None:
    headers = [
        "Length of Stay",
        "Total Charges",
        "APR DRG Code",
        "Payment Typology 1",
        "APR Severity of Illness Code",
        "Source of Payment 1",
    ]
    mapping, unmapped, missing = ingest.resolve_columns(headers, required=())
    assert unmapped == []
    assert missing == set()
    assert mapping["Length of Stay"] == "length_of_stay"
    assert mapping["APR DRG Code"] == "apr_drg_code"
    assert mapping["APR Severity of Illness Code"] == "apr_severity_of_illness"
    assert mapping["Payment Typology 1"] == "payment_typology_1"
    assert mapping["Source of Payment 1"] == "payment_typology_1"


def test_alias_priority_prefers_code_column() -> None:
    preferred = ingest.preferred_sources(
        ["apr_severity_of_illness_code", "apr_severity_of_illness"]
    )
    assert preferred["apr_severity_of_illness"] == "apr_severity_of_illness_code"


def test_2011_style_fixture_resolves_canonically() -> None:
    headers = fixture_headers("sparcs_2011_style.csv")
    mapping, unmapped, missing = ingest.resolve_columns(headers)
    assert missing == set()
    assert unmapped == []
    assert mapping["age"] == "age_group"
    assert mapping["sex"] == "gender"
    assert mapping["apr_drg_description_and_code"] == "apr_drg_code"
    assert mapping["apr_severity_of_illness"] == "apr_severity_of_illness"
    assert mapping["source_of_payment_1"] == "payment_typology_1"


def test_2024_style_fixture_resolves_canonically() -> None:
    headers = fixture_headers("sparcs_2024_style.csv")
    mapping, unmapped, missing = ingest.resolve_columns(headers)
    assert missing == set()
    assert unmapped == []
    assert mapping["ccsr_diagnosis_code"] == "ccsr_diagnosis_code"


def test_missing_required_column_raises(conn: duckdb.DuckDBPyConnection) -> None:
    path = FIXTURES / "sparcs_missing_required.csv"
    with pytest.raises(ingest.IngestionError, match="apr_drg_code"):
        ingest.ingest_file(conn, path, year=2024)


def test_ingest_both_schema_families(conn: duckdb.DuckDBPyConnection) -> None:
    rows_2011 = ingest.ingest_file(conn, FIXTURES / "sparcs_2011_style.csv", 2011)
    rows_2024 = ingest.ingest_file(conn, FIXTURES / "sparcs_2024_style.csv", 2024)
    assert (rows_2011, rows_2024) == (4, 4)

    capped = conn.execute(
        "SELECT length_of_stay, los_capped FROM stg_discharges "
        "WHERE source_year = 2011 AND los_capped"
    ).fetchone()
    assert capped == (120, True)

    money = conn.execute(
        "SELECT total_charges FROM stg_discharges "
        "WHERE source_year = 2024 AND total_charges > 1000000"
    ).fetchone()
    assert money[0] == pytest.approx(1_234_567.89)

    severity = conn.execute(
        "SELECT apr_severity_of_illness FROM stg_discharges "
        "WHERE source_year = 2024 AND apr_drg_code = '302'"
    ).fetchone()
    assert severity == ("2",)

    payer = conn.execute(
        "SELECT payment_typology_1 FROM stg_discharges WHERE source_year = 2011 AND los_capped"
    ).fetchone()
    assert payer == ("Medicaid",)


def test_registry_is_complete_and_current() -> None:
    registry = download.load_registry()
    assert sorted(registry) == list(range(2009, 2025))
    for year, meta in registry.items():
        assert meta["domain"] == "health.data.ny.gov"
        assert re.fullmatch(r"[a-z0-9]{4}-[a-z0-9]{4,6}", meta["id"]), year
        assert meta["rows"] > 1_000_000, year
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["access_date"]), year
        assert meta["clinical_grouping"] in ("CCS", "CCSR")


def test_download_url_construction() -> None:
    meta = {"domain": "health.data.ny.gov", "id": "abcd-1234"}
    assert (
        download.build_url(meta)
        == "https://health.data.ny.gov/api/views/abcd-1234/rows.csv?accessType=DOWNLOAD"
    )
    assert (
        download.build_url(meta, sample_rows=100)
        == "https://health.data.ny.gov/resource/abcd-1234.csv?$limit=100"
    )
