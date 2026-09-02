"""One-command pipeline: ingest raw files, transform, build marts.

Runs against whatever raw files exist in data/raw (sample or full) and
reproduces every mart from raw input:

    python scripts/run_pipeline.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.transform import run_all  # noqa: E402


def main() -> int:
    try:
        row_counts = run_all()
    except Exception as error:  # noqa: BLE001 - command boundary
        print(f"pipeline failed: {error}", file=sys.stderr)
        return 1
    print("marts built:")
    for name, rows in sorted(row_counts.items()):
        print(f"  {name}: {rows} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
