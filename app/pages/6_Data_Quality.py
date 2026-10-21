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
    mart_name="data_quality_summary.parquet",
)

st.markdown("#### Coverage and completeness by year")
SHARE_LABELS = {
    "facility_redacted_share": "Facility redacted",
    "apr_drg_missing_share": "DRG missing",
    "severity_missing_share": "Severity missing",
    "los_missing_share": "LOS missing",
    "ed_indicator_missing_share": "ED indicator missing",
    "payer_unknown_share": "Payer unknown",
    "disposition_missing_share": "Disposition missing",
    "charges_missing_share": "Charges missing",
    "costs_missing_share": "Costs missing",
}
column_config: dict = {
    "year": "Year",
    "source_file": "Source file",
    "rows": st.column_config.NumberColumn("Rows", format=",.0f"),
    "distinct_facilities": st.column_config.NumberColumn("Facilities", format=",.0f"),
    "distinct_apr_drgs": st.column_config.NumberColumn("APR-DRGs", format=",.0f"),
}
for column, label in SHARE_LABELS.items():
    if column in quality.columns:
        column_config[column] = st.column_config.NumberColumn(label, format=".1%")
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
aggregate_scope = (
    "sample" if data.is_demo_mart("data_quality_summary.parquet") else "loaded dataset"
)
st.caption(
    "Redacted share: records whose facility fields were redacted at source "
    f"(for example abortion-related discharges); they count in {aggregate_scope} "
    "totals but never in facility comparisons. LOS capped: source codes "
    "stays of 120 days or more as '120 +', staged as 120 with a flag. "
    "Missing shares sit at or near zero by design; SPARCS is a highly "
    "complete administrative source."
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
metadata = data.load_run_metadata("data_quality_summary.parquet")
if metadata:
    staged = metadata.get("staged_years", [])
    total_rows = sum(entry["rows"] for entry in staged)
    summary_columns = st.columns(3)
    summary_columns[0].metric("Discharge years staged", f"{len(staged)}")
    summary_columns[1].metric("Rows staged", f"{total_rows:,}")
    summary_columns[2].metric("Marts built", f"{len(metadata.get('marts', {}))}")
    with st.expander("Run detail (JSON)"):
        st.json(
            {
                "generated_utc": metadata["generated_utc"],
                "staged_years": {
                    str(entry["year"]): f"{entry['rows']:,} rows, "
                    f"{entry['distinct_facilities']} facilities"
                    for entry in staged
                },
                "marts": {
                    name: f"{meta['rows']:,} rows" for name, meta in metadata["marts"].items()
                },
                "payer_values_mapped_to_other": metadata["payer_values_mapped_to_other"][:10],
            },
            expanded=1,
        )
else:
    st.info("No run metadata was found beside the displayed data-quality mart.")

st.markdown("#### Known limitations")
limitations_path = ROOT / "docs" / "limitations.md"
if limitations_path.exists():
    st.markdown(limitations_path.read_text(encoding="utf-8"))
