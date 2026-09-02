"""One-command pipeline: download, ingest, transform, build marts.

Implemented in Milestone 2. Exists now so the command contract is visible:
`python scripts/run_pipeline.py` reproduces everything from raw input to marts.
"""

import sys


def main() -> int:
    print(
        "run_pipeline is implemented in Milestone 2; no pipeline steps are available yet.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
