"""Data Quality: coverage, completeness, invalid values, schema drift, metadata."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.components import data, theme  # noqa: E402

st.set_page_config(page_title="Data Quality", layout="centered")
theme.apply_theme()

quality = data.load_mart("data_quality_summary.parquet")
theme.page_header(
    "Data quality",
    "What is in the data, what is missing, and what should not be compared?",
    "Coverage, completeness, invalid-value checks, schema drift across annual "
    "files, and pipeline run metadata.",
)

st.markdown("#### Coverage and completeness by year")
share_columns = [
    "facility_redacted_share",
    "apr_drg_missing_share",
    "severity_missing_share",
    "los_missing_share",
    "ed_indicator_missing_share",
    "payer_unknown_share",
    "disposition_missing_share",
    "charges_missing_share",
    "costs_missing_share",
]
column_config: dict = {
    "year": "Year",
    "source_file": "Source file",
    "rows": st.column_config.NumberColumn("Rows", format=",.0f"),
    "distinct_facilities": st.column_config.NumberColumn("Facilities", format=",.0f"),
    "distinct_apr_drgs": st.column_config.NumberColumn("APR-DRGs", format=",.0f"),
}
for column in share_columns:
    if column in quality.columns:
        column_config[column] = st.column_config.NumberColumn(column, format=".1%")
column_config.update(
    {
        "negative_charges": st.column_config.NumberColumn("Negative charges", format=",.0f"),
        "negative_costs": st.column_config.NumberColumn("Negative costs", format=",.0f"),
        "negative_los": st.column_config.NumberColumn("Negative LOS", format=",.0f"),
        "los_capped": st.column_config.NumberColumn("LOS capped at 120+", format=",.0f"),
        "clinical_grouping": "Clinical grouping",
    }
)
st.dataframe(
    quality,
    column_config=column_config,
    hide_index=True,
    width="stretch",
)
st.caption(
    "Redacted share: records whose facility fields were redacted at source "
    "(for example abortion-related discharges); they count in statewide "
    "totals but never in facility comparisons. LOS capped: source codes "
    "stays of 120 days or more as '120 +', staged as 120 with a flag."
)

st.markdown("#### Schema drift across annual files")
report_path = ROOT / "docs" / "schema_report.json"
if report_path.exists():
    report = json.loads(report_path.read_text(encoding="utf-8"))
    drift = pd.DataFrame(
        [
            {
                "Year": int(year),
                "Dataset ID": meta["dataset_id"],
                "Rows": meta["rows"],
                "Columns": meta["column_count"],
                "Grouping": meta["clinical_grouping_family"],
                "Missing canonical fields": len(meta["missing_canonical"]),
            }
            for year, meta in sorted(report["years"].items())
        ]
    )
    st.dataframe(drift, hide_index=True, width="stretch")
    st.caption(
        "CCS (through 2017) and CCSR (2018 onward) families are kept separate "
        "and never forced into one longitudinal mapping; APR-DRG is the "
        "stable cross-year key. Full report: docs/schema_drift.md, generated "
        f"{report['generated_utc']}."
    )
else:
    st.info("Schema report not found (docs/schema_report.json).")

st.markdown("#### Pipeline run metadata")
metadata = data.load_run_metadata()
if metadata:
    st.json(
        {
            "generated_utc": metadata["generated_utc"],
            "staged_years": {
                str(
                    entry["year"]
                ): f"{entry['rows']:,} rows, {entry['distinct_facilities']} facilities"
                for entry in metadata["staged_years"]
            },
            "marts": {name: f"{meta['rows']:,} rows" for name, meta in metadata["marts"].items()},
            "payer_values_mapped_to_other": metadata["payer_values_mapped_to_other"][:10],
        },
        expanded=2,
    )
else:
    st.info("No run metadata found; build marts with scripts/run_pipeline.py.")

st.markdown("#### Known limitations")
limitations_path = ROOT / "docs" / "limitations.md"
if limitations_path.exists():
    st.markdown(limitations_path.read_text(encoding="utf-8"))
