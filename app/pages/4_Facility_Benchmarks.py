"""Facility Benchmarks: case-mix adjusted comparisons across facilities."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.components import charts, data, filters, theme  # noqa: E402
from src.config import (
    MIN_DRG_VOLUME_PER_PERIOD,  # noqa: E402
    MIN_FACILITY_VOLUME_PER_PERIOD,  # noqa: E402
)
from src.metrics import compute_facility_benchmarks  # noqa: E402

st.set_page_config(page_title="Facility Benchmarks", layout="centered")
theme.apply_theme()

detail = data.load_mart("facility_drg_benchmarks.parquet")
benchmark_scope = (
    "sample" if data.is_demo_mart("facility_drg_benchmarks.parquet") else "selected data"
)
theme.page_header(
    "Facility benchmarks",
    f"Which facilities differ from patterns in the {benchmark_scope} after adjusting for case mix?",
    "Cost index compares each facility's estimated cost with the cost implied "
    f"by {benchmark_scope} median rates for the same APR-DRG mix.",
    mart_name="facility_drg_benchmarks.parquet",
)

with st.sidebar:
    st.markdown("#### Filters")
    bounds = filters.year_range(detail)
    counties = filters.multiselect(detail, "county", "County")

scope = filters.apply(detail, year_bounds=bounds, counties=counties)
if scope.empty:
    st.info(
        "No facility-DRG records match the selected filters. Widen the year "
        "range or clear the county filter."
    )
    st.stop()

period = (
    scope.groupby(["facility_id", "facility_name", "county", "apr_drg_code"])
    .agg(
        discharges=("discharges", "sum"),
        estimated_cost=("estimated_cost", "sum"),
        los_days_sum=("los_days_sum", "sum"),
        high_severity_discharges=("high_severity_discharges", "sum"),
    )
    .reset_index()
)
benchmarks = compute_facility_benchmarks(period)
indexed = benchmarks.dropna(subset=["cost_index"])

st.markdown(f"#### Throughput vs cost per discharge, {bounds[0]}-{bounds[1]}")
if indexed.empty:
    st.info(
        "No facility reaches the volume thresholds for this period; "
        "benchmarks are suppressed at low volume by policy."
    )
else:
    median_alos = float(indexed["alos"].median())
    median_cost = float((indexed["estimated_cost"] / indexed["qualifying_discharges"]).median())
    indexed = indexed.assign(
        cost_per_discharge=indexed["estimated_cost"] / indexed["qualifying_discharges"]
    )
    st.plotly_chart(
        charts.bubble_scatter(
            indexed["alos"],
            indexed["cost_per_discharge"],
            indexed["qualifying_discharges"],
            indexed["facility_name"],
            median_alos,
            median_cost,
            "ALOS (days)",
            "Estimated cost per discharge",
            median_label=f"{benchmark_scope} median",
        ),
        width="stretch",
        key="benchmark_scatter",
    )
    st.caption(
        f"Point size: qualifying discharges. Dashed lines: {benchmark_scope} facility "
        "medians. Position above or right of the medians is a signal for "
        "investigation, not a finding of inefficiency."
    )

st.markdown("#### Ranked facilities")
table = benchmarks.sort_values("cost_index", ascending=False, na_position="last")
st.dataframe(
    table,
    column_config={
        "facility_name": "Facility",
        "county": "County",
        "total_discharges": st.column_config.NumberColumn("Discharges (period)", format=",.0f"),
        "qualifying_drgs": st.column_config.NumberColumn("Qualifying DRGs", format=",.0f"),
        "qualifying_discharges": st.column_config.NumberColumn(
            "Qualifying discharges", format=",.0f"
        ),
        "suppressed_drg_comparisons": st.column_config.NumberColumn(
            "Suppressed comparisons", format=",.0f"
        ),
        "estimated_cost": st.column_config.NumberColumn("Estimated cost", format="$,.0f"),
        "expected_benchmark_cost": st.column_config.NumberColumn(
            "Expected at median rates", format="$,.0f"
        ),
        "cost_index": st.column_config.NumberColumn("Cost index", format=".2f"),
        "cost_index_percentile": st.column_config.NumberColumn("Percentile", format=".1f"),
        "alos": st.column_config.NumberColumn("ALOS", format=".1f"),
        "high_severity_share": st.column_config.NumberColumn("High-severity share", format=".1%"),
        "status": "Status",
        "facility_id": None,
    },
    hide_index=True,
    width="stretch",
    height=420,
)
data.download_button(table, "facility_benchmarks.csv", "Download benchmarks (CSV)")

with st.expander("Benchmark methodology"):
    st.markdown(
        "- Index = total estimated cost / expected cost, where expected cost "
        f"prices each qualifying facility-DRG volume at the {benchmark_scope} median "
        "cost per discharge for that DRG (indirect standardization: the case "
        "mix self-weights the rollup).\n"
        "- DRG medians are facility-level medians among qualifying "
        "facilities, so a single large facility cannot define the benchmark.\n"
        f"- Qualifying comparisons need at least {MIN_DRG_VOLUME_PER_PERIOD} "
        "facility-DRG discharges in the period; suppressed comparisons are "
        "counted in the table, never silently dropped.\n"
        f"- Facilities under {MIN_FACILITY_VOLUME_PER_PERIOD} total discharges "
        "in the period are suppressed (no index) and flagged.\n"
        "- Percentile ranks use average ranks among indexed facilities. "
        "Redacted-facility records are excluded from this page entirely."
    )

theme.definitions_expander()
