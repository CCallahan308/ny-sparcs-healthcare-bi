"""Copy the current sample-built marts into the committed demo_marts/ set.

The full SPARCS extracts are far too large for a git repository or a hosted
app tier, so the repository carries marts built from the 50k-row public
samples instead. A fresh clone (or a Streamlit Community Cloud deployment)
renders the full app from these; anyone who runs the pipeline against the
full downloads gets the real marts locally, which always take precedence.

Run after rebuilding marts from sample data:

    python -m src.download --sample 50000 --years 2009 2011 2024
    python scripts/run_pipeline.py
    python scripts/export_demo_marts.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import DEMO_MARTS_DIR, MART_EXPORTS, MARTS_DIR  # noqa: E402

MAX_TOTAL_BYTES = 5 * 1024 * 1024


def main() -> int:
    DEMO_MARTS_DIR.mkdir(parents=True, exist_ok=True)
    sources = [*MART_EXPORTS.values(), "run_metadata.json"]
    total = 0
    for name in sources:
        source = MARTS_DIR / name
        if not source.exists():
            print(f"missing {source}; run scripts/run_pipeline.py first", file=sys.stderr)
            return 1
        destination = DEMO_MARTS_DIR / name
        shutil.copy2(source, destination)
        size = destination.stat().st_size
        total += size
        print(f"{name:40s} {size:>10,} bytes")
    print(f"{'TOTAL':40s} {total:>10,} bytes")
    if total > MAX_TOTAL_BYTES:
        print(
            f"demo marts exceed {MAX_TOTAL_BYTES:,} bytes; "
            "rebuild from smaller samples before committing",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
