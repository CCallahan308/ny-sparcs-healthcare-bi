"""Central configuration: deterministic paths, logging, and shared constants.

All paths derive from PROJECT_ROOT so the pipeline runs from any working
directory with no hardcoded local absolute paths.
"""

from __future__ import annotations

import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MARTS_DIR = DATA_DIR / "marts"
DUCKDB_PATH = PROCESSED_DIR / "sparcs.duckdb"

HISTORY_START_YEAR = 2009
DEFAULT_START_YEAR = 2019
DEFAULT_END_YEAR = 2024

# 2020 is treated as an assignable-cause period: excluded from baseline
# control-limit calculation by default, retained in displayed series.
EXCLUDED_BASELINE_YEARS = frozenset({2020})


def ensure_data_dirs() -> None:
    """Create the data directory tree if missing."""
    for directory in (RAW_DIR, PROCESSED_DIR, MARTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """Return a logger with a consistent format, safe to call repeatedly."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
