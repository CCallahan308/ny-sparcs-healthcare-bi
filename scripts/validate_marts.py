"""Validate generated marts: presence, negatives, year coverage, reconciliation.

python scripts/validate_marts.py
"""

import sys
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DUCKDB_PATH, MARTS_DIR  # noqa: E402
from src.quality import validate_marts  # noqa: E402


def main() -> int:
    if not DUCKDB_PATH.exists():
        print(
            f"no DuckDB database at {DUCKDB_PATH}; run scripts/run_pipeline.py first",
            file=sys.stderr,
        )
        return 1
    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        issues = validate_marts(conn, MARTS_DIR)
    finally:
        conn.close()
    if issues:
        print("VALIDATION FAILED:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print("all mart checks passed: presence, negatives, year coverage, reconciliation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
