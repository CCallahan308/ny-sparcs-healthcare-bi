"""Execute SQL staging and mart transformations into Parquet marts.

SQL files hold the business transformations; this module only sequences,
executes, and exports. Table-to-file mapping keeps COPY targets configurable
without editing SQL.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from src.config import (
    DUCKDB_PATH,
    MART_EXPORTS,
    MARTS_DIR,
    PROJECT_ROOT,
    ensure_data_dirs,
    get_logger,
)
from src.ingest import discover_raw_files, ingest_file, reset_staging
from src.quality import write_run_metadata

logger = get_logger(__name__)

SQL_STAGING_DIR = PROJECT_ROOT / "sql" / "staging"
SQL_MARTS_DIR = PROJECT_ROOT / "sql" / "marts"


def execute_sql_dir(conn: duckdb.DuckDBPyConnection, directory: Path) -> None:
    """Run every .sql file in a directory in filename order."""
    sql_files = sorted(directory.glob("*.sql"))
    if not sql_files:
        raise FileNotFoundError(f"no SQL files found in {directory}")
    for sql_file in sql_files:
        logger.info("executing %s", sql_file.name)
        conn.execute(sql_file.read_text(encoding="utf-8"))


def export_marts(conn: duckdb.DuckDBPyConnection, marts_dir: Path) -> dict[str, int]:
    """Write every mart table to Parquet; returns row counts per mart."""
    marts_dir.mkdir(parents=True, exist_ok=True)
    row_counts: dict[str, int] = {}
    for table, file_name in MART_EXPORTS.items():
        destination = marts_dir / file_name
        conn.execute(
            f"COPY {table} TO '{destination.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        row_counts[file_name] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        logger.info("%s: %s rows", file_name, row_counts[file_name])
    return row_counts


def run_transformations(conn: duckdb.DuckDBPyConnection, marts_dir: Path) -> dict[str, int]:
    """Normalize staging and build every mart table."""
    execute_sql_dir(conn, SQL_STAGING_DIR)
    execute_sql_dir(conn, SQL_MARTS_DIR)
    return export_marts(conn, marts_dir)


def run_all(db_path: Path = DUCKDB_PATH, marts_dir: Path = MARTS_DIR) -> dict[str, int]:
    """One-command pipeline: ingest raw files, transform, export marts."""
    ensure_data_dirs()
    marts_dir.mkdir(parents=True, exist_ok=True)
    files = discover_raw_files()
    if not files:
        raise FileNotFoundError("no raw SPARCS files found; run `python -m src.download` first")
    conn = duckdb.connect(str(db_path))
    try:
        reset_staging(conn)
        for year, path in sorted(files.items()):
            ingest_file(conn, path, year)
        row_counts = run_transformations(conn, marts_dir)
        write_run_metadata(conn, marts_dir, row_counts, files)
    finally:
        conn.close()
    return row_counts


def main() -> int:
    try:
        run_all()
    except Exception as error:  # noqa: BLE001 - top-level command boundary
        logger.error("pipeline failed: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
