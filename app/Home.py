"""Home: the business problem, what each page answers, and the ground rules."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.components import data, theme  # noqa: E402

theme.apply_theme()
st.set_page_config(page_title="NY SPARCS Healthcare Operations BI", page_icon=None)

theme.page_header(
    "NY SPARCS Healthcare Operations BI",
    "Where do cost and throughput concentrate, and which facilities stand out?",
    "In-house analytics on New York State's public, de-identified inpatient "
    "discharge data (SPARCS), 2009-2024.",
)

st.markdown(
    """
New York hospital systems operate on thin margins driven by payer mix, case
complexity, and length of stay. This system gives a finance and operations
committee one view of where estimated cost and throughput concentrate by
facility, service line, and payer, which facilities show potential outlier
signals after accounting for case mix, and which annual metrics have moved
beyond their historical process behavior.
"""
)

st.markdown("#### What each page answers")
page_guide = [
    (
        "Executive Summary",
        "Where do volume, cost, and throughput stand for the selected scope, "
        "and how do they compare with the prior year?",
    ),
    (
        "Service Lines",
        "Which service lines and APR-DRGs concentrate estimated cost, and which are moving?",
    ),
    (
        "Payer Exposure",
        "How are discharges and estimated cost distributed across payer "
        "classes, and how concentrated is that exposure?",
    ),
    (
        "Facility Benchmarks",
        "Which facilities differ from statewide patterns after adjusting for "
        "case mix, and by how much?",
    ),
    (
        "Process Control",
        "Which annual metrics show signals for investigation rather than routine variation?",
    ),
    (
        "Data Quality",
        "What is in the data, what is missing, and what should not be compared across years?",
    ),
]
st.markdown(
    "| Page | Business question |\n|---|---|\n"
    + "".join(f"| {page} | {question} |\n" for page, question in page_guide)
)

metadata = data.load_run_metadata()
if metadata:
    years = [entry["year"] for entry in metadata["staged_years"]]
    rows = sum(entry["rows"] for entry in metadata["staged_years"])
    st.markdown("#### Current build")
    st.markdown(
        f"- Discharge records staged: {rows:,} across {len(years)} years "
        f"({min(years)} to {max(years)}).\n"
        f"- Marts built {metadata['generated_utc']} by `scripts/run_pipeline.py`.\n"
        "- Estimated costs are DOH-derived estimates; charges are not reimbursement."
    )
else:
    st.info(
        "No marts have been built yet. Run `python scripts/run_pipeline.py` to "
        "build them from downloaded SPARCS files."
    )

theme.definitions_expander()

st.markdown(
    '<div class="caption">Source: Hospital Inpatient Discharges (SPARCS '
    "De-Identified), New York State Department of Health, health.data.ny.gov. "
    "Public use data; no patient-level records.</div>",
    unsafe_allow_html=True,
)
