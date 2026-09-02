"""Data quality validation and pipeline run metadata.

validate_marts runs the same checks from scripts/validate_marts.py so the
quality gates are runnable standalone and from CI (against committed marts
or a fresh build).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from src.config import MART_EXPORTS, get_logger

logger = get_logger(__name__)

MEASURE_COLUMNS = {
    "discharges",
    "estimated_cost",
    "total_charges",
    "los_days_sum",
    "high_severity_discharges",
    "ed_origin_discharges",
    "post_acute_discharges",
    "numerator",
}


def validate_marts(conn: duckdb.DuckDBPyConnection, marts_dir: Path) -> list[str]:
    """Return a list of issues; an empty list means every check passed."""
    issues: list[str] = []

    staging_years = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT discharge_year FROM stg_normalized ORDER BY 1"
        ).fetchall()
    }
    staging_totals = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(total_costs), 0) FROM stg_normalized"
    ).fetchone()

    for file_name in MART_EXPORTS.values():
        path = marts_dir / file_name
        if not path.exists() or path.stat().st_size == 0:
            issues.append(f"{file_name}: missing or empty")
            continue

        relation = conn.sql(f"SELECT * FROM read_parquet('{path.as_posix()}')")
        columns = set(relation.columns)

        for column in MEASURE_COLUMNS & columns:
            negative = conn.execute(
                f"SELECT COUNT(*) FROM read_parquet('{path.as_posix()}') WHERE {column} < 0"
            ).fetchone()[0]
            if negative:
                issues.append(f"{file_name}: {negative} negative values in {column}")

        if "discharge_year" in columns:
            mart_years = {
                row[0]
                for row in conn.execute(
                    f"SELECT DISTINCT discharge_year FROM read_parquet('{path.as_posix()}')"
                ).fetchall()
            }
            if mart_years != staging_years:
                issues.append(
                    f"{file_name}: year coverage {sorted(mart_years)} != "
                    f"staging {sorted(staging_years)}"
                )

    # Reconciliation: statewide executive trends must match staging totals.
    trends_path = marts_dir / "executive_trends.parquet"
    if trends_path.exists():
        trends = conn.execute(
            f"SELECT SUM(discharges), SUM(estimated_cost) FROM "
            f"read_parquet('{trends_path.as_posix()}')"
        ).fetchone()
        if trends[0] != staging_totals[0]:
            issues.append(
                f"reconciliation: trends discharges {trends[0]} != staging {staging_totals[0]}"
            )
        if abs((trends[1] or 0) - (staging_totals[1] or 0)) > 0.01:
            issues.append(
                f"reconciliation: trends estimated_cost {trends[1]} != staging {staging_totals[1]}"
            )
    return issues


def write_run_metadata(
    conn: duckdb.DuckDBPyConnection,
    marts_dir: Path,
    mart_row_counts: dict[str, int],
    source_files: dict[int, Path],
) -> None:
    """Record what was built, from what, and which payer values fell to 'Other'."""
    per_year = conn.execute(
        """
        SELECT discharge_year, source_file, COUNT(*),
            COUNT(DISTINCT facility_id) FILTER (WHERE NOT facility_redacted)
        FROM stg_normalized
        GROUP BY 1, 2
        ORDER BY 1
        """
    ).fetchall()
    unmapped_payers = conn.execute(
        """
        SELECT discharge_year, payer_raw, COUNT(*)
        FROM stg_normalized
        WHERE payer_class = 'Other'
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
        """
    ).fetchall()
    metadata = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_files": {
            str(year): {"name": path.name, "bytes": path.stat().st_size}
            for year, path in sorted(source_files.items())
        },
        "staged_years": [
            {
                "year": int(year),
                "source_file": source_file,
                "rows": int(rows),
                "distinct_facilities": int(facilities),
            }
            for year, source_file, rows, facilities in per_year
        ],
        "marts": {name: {"rows": rows} for name, rows in sorted(mart_row_counts.items())},
        "payer_values_mapped_to_other": [
            {"year": int(year), "payer_raw": payer_raw, "rows": int(count)}
            for year, payer_raw, count in unmapped_payers
        ],
    }
    destination = marts_dir / "run_metadata.json"
    destination.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    logger.info("run metadata written: %s", destination)
