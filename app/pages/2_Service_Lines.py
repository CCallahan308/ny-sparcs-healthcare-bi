"""Service Lines: where cost, volume, and severity concentrate, and movers."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.components import charts, data, filters, theme  # noqa: E402
from src.config import MIN_DRG_VOLUME_PER_PERIOD  # noqa: E402

st.set_page_config(page_title="Service Lines", layout="centered")
theme.apply_theme()

lines = data.load_mart("service_line_summary.parquet")
theme.page_header(
    "Service lines",
    "Which service lines and APR-DRGs concentrate estimated cost?",
    "Service line = APR Major Diagnostic Category (MDC). APR-DRG is the "
    "stable cross-year clinical grouping key.",
)

with st.sidebar:
    st.markdown("#### Filters")
    bounds = filters.year_range(lines)
    service_lines = filters.multiselect(lines, "mdc_description", "Service line")

scope = filters.apply(lines, year_bounds=bounds, service_lines=service_lines)

if scope.empty:
    st.info(
        "No discharges match the selected filters. Widen the year range or "
        "clear the service-line filter."
    )
    st.stop()

summary = (
    scope.groupby(["mdc_description", "apr_drg_code", "apr_drg_description"])
    .agg(
        discharges=("discharges", "sum"),
        estimated_cost=("estimated_cost", "sum"),
        los_days_sum=("los_days_sum", "sum"),
        high_severity_discharges=("high_severity_discharges", "sum"),
    )
    .reset_index()
)
summary["cost_per_discharge"] = summary["estimated_cost"] / summary["discharges"]
summary["alos"] = summary["los_days_sum"] / summary["discharges"]
summary["high_severity_share"] = summary["high_severity_discharges"] / summary["discharges"]

st.markdown("#### Top 15 APR-DRGs by estimated cost")
top = summary.nlargest(15, "estimated_cost").sort_values("estimated_cost")
st.plotly_chart(
    charts.horizontal_ranked_bar(
        [f"{row.apr_drg_description} ({row.apr_drg_code})" for row in top.itertuples()],
        top["estimated_cost"],
        y_prefix="$",
    ),
    width="stretch",
    key="drg_cost_bar",
)
st.caption(
    f"Grain: APR-DRG aggregated over {bounds[0]}-{bounds[1]} and the selected "
    "service lines. Units: total estimated cost."
)

st.markdown("#### Severity mix for the same top 15")
severity = summary.nlargest(15, "estimated_cost")
severity = severity.assign(
    drg_label=[
        f"{code}: {description[:38]}{'...' if len(description) > 38 else ''}"
        for code, description in zip(
            severity["apr_drg_code"], severity["apr_drg_description"], strict=True
        )
    ],
    low=1 - severity["high_severity_share"],
    high=severity["high_severity_share"],
).set_index("drg_label")[["low", "high"]]
st.plotly_chart(
    charts.horizontal_stacked_share(
        severity,
        colors={"low": "#C6DCD8", "high": "#0F6E63"},
    ),
    width="stretch",
    key="drg_severity_mix",
)
st.caption(
    "High severity = APR severity-of-illness 3 or 4. Severity code 0 "
    "(unclassified) counts as not high. Denominator: discharges per DRG."
)

st.markdown("#### Service line and APR-DRG detail")
table = summary.sort_values("estimated_cost", ascending=False)
st.dataframe(
    table,
    column_config={
        "mdc_description": "Service line (MDC)",
        "apr_drg_code": "APR-DRG",
        "apr_drg_description": "APR-DRG description",
        "discharges": st.column_config.NumberColumn("Discharges", format=",.0f"),
        "estimated_cost": st.column_config.NumberColumn("Estimated cost", format="$,.0f"),
        "cost_per_discharge": st.column_config.NumberColumn(
            "Est. cost / discharge", format="$,.0f"
        ),
        "alos": st.column_config.NumberColumn("ALOS", format=".1f"),
        "high_severity_share": st.column_config.NumberColumn("High-severity share", format=".1%"),
        "los_days_sum": None,
        "high_severity_discharges": None,
    },
    hide_index=True,
    width="stretch",
    height=420,
)
data.download_button(table, "service_line_detail.csv", "Download service line detail (CSV)")

first_year = int(scope["discharge_year"].min())
last_year = int(scope["discharge_year"].max())
if first_year < last_year:
    st.markdown(f"#### Top movers, {first_year} to {last_year}")
    endpoints = scope[scope["discharge_year"].isin([first_year, last_year])]
    pivot = endpoints.pivot_table(
        index=["apr_drg_code", "apr_drg_description"],
        columns="discharge_year",
        values=["discharges", "estimated_cost"],
        aggfunc="sum",
    ).fillna(0)
    pivot = pivot[
        (pivot[("discharges", first_year)] >= MIN_DRG_VOLUME_PER_PERIOD)
        & (pivot[("discharges", last_year)] >= MIN_DRG_VOLUME_PER_PERIOD)
    ].copy()
    pivot["discharge_change"] = (
        pivot[("discharges", last_year)] / pivot[("discharges", first_year)] - 1
    )
    pivot["cost_change"] = (
        pivot[("estimated_cost", last_year)] / pivot[("estimated_cost", first_year)] - 1
    )
    movers = pivot.reset_index().sort_values("discharge_change", ascending=False)
    up = movers.head(5)[["apr_drg_description", "apr_drg_code", "discharge_change", "cost_change"]]
    down = movers.tail(5).sort_values("discharge_change")[
        ["apr_drg_description", "apr_drg_code", "discharge_change", "cost_change"]
    ]
    left, right = st.columns(2)
    with left:
        st.markdown("Largest volume increases")
        st.dataframe(
            up,
            column_config={
                "apr_drg_description": "APR-DRG",
                "apr_drg_code": None,
                "discharge_change": st.column_config.NumberColumn(
                    "Discharge change", format="+.1%"
                ),
                "cost_change": st.column_config.NumberColumn("Cost change", format="+.1%"),
            },
            hide_index=True,
            width="stretch",
        )
    with right:
        st.markdown("Largest volume decreases")
        st.dataframe(
            down,
            column_config={
                "apr_drg_description": "APR-DRG",
                "apr_drg_code": None,
                "discharge_change": st.column_config.NumberColumn(
                    "Discharge change", format="+.1%"
                ),
                "cost_change": st.column_config.NumberColumn("Cost change", format="+.1%"),
            },
            hide_index=True,
            width="stretch",
        )
    st.caption(
        f"Mover rule: percent change between endpoint years {first_year} and "
        f"{last_year}, restricted to APR-DRGs with at least "
        f"{MIN_DRG_VOLUME_PER_PERIOD} discharges in both endpoint years. "
        "APR-DRG is stable across years; CCS and CCSR categories are never "
        "compared across the 2018 boundary."
    )
else:
    st.info(
        "Top movers need at least two years inside the selected range; only "
        f"{first_year} is present, so no period-over-period change is computed."
    )

theme.definitions_expander()
