"""Visual system: restrained neutrals, one accent, one alert color.

No gradients, no hero text, no decorative icons. Accent marks selection and
data; the alert color marks defined exception rules only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ACCENT = "#0F6E63"
ACCENT_SOFT = "#4C9A8E"
ACCENT_PALE = "#8FC3BA"
ALERT = "#B3261E"
TEXT = "#2B2F2E"
MUTED = "#5A6260"
GRID = "#E4E7E6"
PANEL = "#F8F9F9"

PAYER_COLORS = {
    "Medicare": "#0F6E63",
    "Medicaid": "#4C9A8E",
    "Private": "#8FC3BA",
    "Managed Care": "#C6DCD8",
    "Self-Pay": "#B48A2F",
    "Other Government": "#9AA3A1",
    "Other": "#D5DAD9",
    "Unknown": "#EDEFEF",
}

FONT_STACK = "Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"

_CSS = """
<style>
  .block-container {max-width: 1180px; padding-top: 2.0rem; padding-bottom: 3rem;}
  [data-testid="stHeader"] {background: #FFFFFF;}
  [data-testid="stMetric"] {background: #F8F9F9; border: 1px solid #E5E8E7;
    border-radius: 6px; padding: 14px 16px;}
  [data-testid="stMetricLabel"] p {font-size: 13px; color: #5A6260;}
  [data-testid="stMetricValue"] {font-size: 25px; font-weight: 600; color: #2B2F2E;}
  .kicker {font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
    color: #5A6260; font-weight: 600; margin-bottom: 2px;}
  h1 {font-size: 27px; color: #2B2F2E; margin-bottom: 3px; font-weight: 650;}
  .subhead {color: #5A6260; font-size: 15px; margin-bottom: 4px;}
  h3 {font-size: 17px; color: #2B2F2E;}
  h4 {font-size: 15px; color: #2B2F2E; margin-bottom: 6px;}
  .caption {color: #5A6260; font-size: 12.5px;}
  [data-testid="stSidebar"] {background: #F7F8F8;}
  [data-testid="stSidebar"] * {font-size: 13.5px;}
  [data-baseweb="slider"] [role="track"] {background: #DCE4E2 !important;}
  [data-baseweb="slider"] [role="track"] > div {background: #9FBFBA !important;}
</style>
"""


def apply_theme() -> None:
    """Inject the visual system. Idempotent; called at the top of every page."""
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(kicker: str, title: str, subhead: str) -> None:
    """Consistent page header: context line, business question, scope note."""
    st.markdown(f'<div class="kicker">{kicker}</div>', unsafe_allow_html=True)
    st.markdown(f"# {title}")
    st.markdown(f'<div class="subhead">{subhead}</div>', unsafe_allow_html=True)
    st.markdown("")


def definitions_expander() -> None:
    """Visible definitions and limitations, on every analytical page."""
    with st.expander("Definitions and limitations"):
        st.markdown(
            "- Time grain is annual; the de-identified source strips day and month.\n"
            "- Costs are DOH-derived estimates; charges are never reimbursement.\n"
            "- Payer views are exposure (share of discharges and estimated cost), "
            "not margin.\n"
            "- Facility comparisons are APR-DRG-aware and suppressed at low volume.\n"
            "- 2020 is an assignable-cause period: shown in series, excluded from "
            "control-chart baselines.\n"
            "- Signals are for investigation, never causal findings."
        )
