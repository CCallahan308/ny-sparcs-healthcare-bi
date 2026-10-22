"""Persistent sidebar filters shared across pages.

Multiselects default to empty, meaning "all values". Applying a filter that
matches nothing produces a graceful empty state on every page.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from src.config import DEFAULT_START_YEAR


def year_range(
    frame: pd.DataFrame,
    key: str = "year_range",
    label: str = "Year range",
    *,
    include_all_years: bool = False,
) -> tuple[int, int]:
    """Select all sample years, or start local builds at 2019 when available."""
    years = sorted(int(year) for year in frame["discharge_year"].unique())
    lo, hi = years[0], years[-1]
    default_start = (
        DEFAULT_START_YEAR if not include_all_years and DEFAULT_START_YEAR in years else lo
    )
    return st.slider(label, lo, hi, (default_start, hi), key=key)


def multiselect(
    frame: pd.DataFrame,
    column: str,
    label: str,
    key: str | None = None,
) -> list[str] | None:
    """Optional multiselect; empty selection means all values."""
    options = sorted(frame[column].dropna().unique().tolist())
    if not options:
        return None
    selected = st.multiselect(f"{label} (empty = all)", options, key=key)
    return selected or None


def apply(
    frame: pd.DataFrame,
    year_bounds: tuple[int, int] | None = None,
    counties: list[str] | None = None,
    facilities: list[str] | None = None,
    payers: list[str] | None = None,
    service_lines: list[str] | None = None,
    drg_codes: list[str] | None = None,
) -> pd.DataFrame:
    scope = frame
    if year_bounds is not None:
        scope = scope[scope["discharge_year"].between(year_bounds[0], year_bounds[1])]
    if counties:
        scope = scope[scope["county"].isin(counties)]
    if facilities:
        scope = scope[scope["facility_name"].isin(facilities)]
    if payers:
        scope = scope[scope["payer_class"].isin(payers)]
    if service_lines:
        scope = scope[scope["mdc_description"].isin(service_lines)]
    if drg_codes:
        scope = scope[scope["apr_drg_code"].isin(drg_codes)]
    return scope
