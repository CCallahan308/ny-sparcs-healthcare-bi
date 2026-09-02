"""Cached mart access. Pages read Parquet marts only, never raw CSVs.

Cache invalidation is tied to file modification time: rebuilding marts
invalidates the cache without manual refresh.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config, metrics  # noqa: E402


def marts_dir() -> Path:
    return config.MARTS_DIR


def resolve_mart_path(file_name: str) -> Path | None:
    """Locally built marts win; committed demo marts serve as the fallback."""
    local = config.MARTS_DIR / file_name
    if local.exists():
        return local
    demo = config.DEMO_MARTS_DIR / file_name
    if demo.exists():
        return demo
    return None


@st.cache_data(show_spinner=False)
def _read_parquet(path_str: str, _mtime: float) -> pd.DataFrame:
    return pd.read_parquet(path_str)


def load_mart(file_name: str) -> pd.DataFrame:
    """Load a mart with a clear failure message when it is missing."""
    path = resolve_mart_path(file_name)
    if path is None:
        st.error(
            f"Required mart is missing: {file_name}. "
            "Build it with `python scripts/run_pipeline.py` first."
        )
        st.stop()
    return _read_parquet(str(path), path.stat().st_mtime)


def load_run_metadata() -> dict | None:
    """Pipeline run metadata, or None before the first build."""
    path = resolve_mart_path("run_metadata.json")
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compute_kpis(frame: pd.DataFrame) -> dict[str, float | None]:
    """Roll up an executive-KPI-grain frame through the metric definitions.

    Every KPI on the Executive Summary derives from this function, which is
    why page numbers and `tests/test_marts.py` cannot drift apart.
    """
    discharges = int(frame["discharges"].sum())
    estimated_cost = float(frame["estimated_cost"].sum())
    los_days = int(frame["los_days_sum"].sum())
    return {
        "discharges": metrics.discharges(discharges),
        "estimated_cost": estimated_cost,
        "cost_per_discharge": metrics.cost_per_discharge(estimated_cost, discharges),
        "cost_per_day": metrics.cost_per_day(estimated_cost, los_days),
        "alos": metrics.alos(los_days, discharges),
        "high_severity_share": metrics.high_severity_share(
            int(frame["high_severity_discharges"].sum()), discharges
        ),
        "ed_origin_rate": metrics.ed_origin_rate(
            int(frame["ed_origin_discharges"].sum()), discharges
        ),
        "post_acute_rate": metrics.post_acute_rate(
            int(frame["post_acute_discharges"].sum()), discharges
        ),
    }


def download_button(frame: pd.DataFrame, file_name: str, label: str) -> None:
    """Small, consistent CSV export for data tables."""
    st.download_button(
        label,
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
    )
