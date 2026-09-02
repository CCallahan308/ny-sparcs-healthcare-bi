"""Shared pytest fixtures: fixture-file pipeline connections."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from src import ingest
from src.transform import SQL_STAGING_DIR, execute_sql_dir

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_YEARS = {
    "sparcs_2009_style.csv": 2009,
    "sparcs_2011_style.csv": 2011,
    "sparcs_2024_style.csv": 2024,
}


@pytest.fixture()
def staging_conn() -> duckdb.DuckDBPyConnection:
    """Raw staging loaded with all three schema-era fixtures."""
    conn = duckdb.connect()
    ingest.ensure_staging(conn)
    for name, year in FIXTURE_YEARS.items():
        ingest.ingest_file(conn, FIXTURES / name, year)
    yield conn
    conn.close()


@pytest.fixture()
def pipeline_conn(staging_conn: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """Normalized staging built from the fixture files."""
    execute_sql_dir(staging_conn, SQL_STAGING_DIR)
    yield staging_conn
