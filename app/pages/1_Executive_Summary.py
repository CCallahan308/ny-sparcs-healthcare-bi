"""Executive Summary: volume, cost, throughput, exposure, prior-year deltas."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.components import charts, data, filters, theme  # noqa: E402
from app.components import formatting as fmt  # noqa: E402

st.set_page_config(page_title="Executive Summary", layout="centered")
theme.apply_theme()

kpis = data.load_mart("executive_kpis.parquet")
theme.page_header(
    "Executive summary",
    "Where do volume, cost, and throughput stand?",
    "All KPIs derive from the executive KPIs mart through the documented "
    "metric definitions; the denominator is discharges in the selected scope.",
    mart_name="executive_kpis.parquet",
)

with st.sidebar:
    st.markdown("#### Filters")
    bounds = filters.year_range(kpis)
    counties = filters.multiselect(kpis, "county", "County")
    facilities = filters.multiselect(kpis, "facility_name", "Facility")
    payers = filters.multiselect(kpis, "payer_class", "Payer class")
    service_lines = filters.multiselect(kpis, "mdc_description", "Service line")

scope = filters.apply(
    kpis,
    year_bounds=bounds,
    counties=counties,
    facilities=facilities,
    payers=payers,
    service_lines=service_lines,
)

if scope.empty:
    st.info(
        "No discharges match the selected filters. Widen the year range or "
        "clear a filter (empty multiselect means all values)."
    )
    st.stop()

current_year = int(scope["discharge_year"].max())
prior_years = scope[scope["discharge_year"] < current_year]["discharge_year"]
prior_year = int(prior_years.max()) if not prior_years.empty else None

current = data.compute_kpis(scope[scope["discharge_year"] == current_year])
prior = data.compute_kpis(scope[scope["discharge_year"] == prior_year]) if prior_year else None

st.markdown(
    f"### Focus year: {current_year}"
    + (f" (deltas vs {prior_year})" if prior_year else " (no prior year in scope)")
)

cards = [
    (
        "Discharges",
        fmt.fmt_int(current["discharges"]),
        fmt.pct_delta(current["discharges"], prior and prior["discharges"]),
    ),
    (
        "Est. cost / discharge",
        fmt.fmt_dollars(current["cost_per_discharge"]),
        fmt.pct_delta(current["cost_per_discharge"], prior and prior["cost_per_discharge"]),
    ),
    (
        "Est. cost / day",
        fmt.fmt_dollars(current["cost_per_day"]),
        fmt.pct_delta(current["cost_per_day"], prior and prior["cost_per_day"]),
    ),
    (
        "ALOS (days)",
        fmt.fmt_alos(current["alos"]),
        fmt.pct_delta(current["alos"], prior and prior["alos"]),
    ),
    (
        "High-severity share",
        fmt.fmt_pct(current["high_severity_share"]),
        fmt.pct_delta(current["high_severity_share"], prior and prior["high_severity_share"]),
    ),
    (
        "ED-origin rate",
        fmt.fmt_pct(current["ed_origin_rate"]),
        fmt.pct_delta(current["ed_origin_rate"], prior and prior["ed_origin_rate"]),
    ),
]
columns = st.columns(3)
for index, (label, value, delta) in enumerate(cards):
    columns[index % 3].metric(label, value, delta, delta_color="off")

st.caption(
    "Cards show the focus year with period-over-period deltas; the charts "
    "below cover the full selected range. Grain: year x facility x county x "
    "service line x payer class, aggregated to the selected scope. Estimated "
    "costs only; deltas carry no direction judgment."
)

yearly = (
    scope.groupby("discharge_year")
    .agg(
        discharges=("discharges", "sum"),
        estimated_cost=("estimated_cost", "sum"),
        los_days_sum=("los_days_sum", "sum"),
        high_severity_discharges=("high_severity_discharges", "sum"),
    )
    .sort_index()
)
yearly["cost_per_discharge"] = yearly["estimated_cost"] / yearly["discharges"]
yearly["alos"] = yearly["los_days_sum"] / yearly["discharges"]
yearly["high_severity_share"] = yearly["high_severity_discharges"] / yearly["discharges"]

chart_specs = [
    ("Discharges by year", yearly["discharges"], ""),
    ("Estimated cost per discharge", yearly["cost_per_discharge"], "$"),
    ("Average length of stay (days)", yearly["alos"], ""),
    ("High-severity share of discharges", yearly["high_severity_share"], ""),
]
left, right = st.columns(2)
for index, (title, series, prefix) in enumerate(chart_specs):
    target = left if index % 2 == 0 else right
    with target:
        st.markdown(f"#### {title}")
        st.plotly_chart(
            charts.line_chart(series.index, series, y_prefix=prefix),
            width="stretch",
            key=f"trend_{index}",
        )
st.caption(
    "Annual grain only; the de-identified source strips month and day. "
    "Series cover the selected scope and years."
)

st.markdown("#### Payer exposure: share of discharges vs share of estimated cost")
latest = scope[scope["discharge_year"] == current_year]
by_payer = (
    latest.groupby("payer_class")
    .agg(discharges=("discharges", "sum"), estimated_cost=("estimated_cost", "sum"))
    .sort_values("discharges", ascending=False)
)
share_discharges = (by_payer["discharges"] / by_payer["discharges"].sum()).tolist()
share_cost = (by_payer["estimated_cost"] / by_payer["estimated_cost"].sum()).tolist()
st.plotly_chart(
    charts.grouped_share_bars(
        by_payer.index.tolist(),
        {
            "Share of discharges": share_discharges,
            "Share of estimated cost": share_cost,
        },
        colors={"Share of discharges": "#8FC3BA", "Share of estimated cost": "#0F6E63"},
    ),
    width="stretch",
    key="payer_exposure",
)
st.caption(
    f"{current_year}, selected scope. Exposure only: the source carries no "
    "payment amounts, so this is not reimbursement, revenue, or margin."
)

if prior:
    st.info(
        f"In the selected scope, {fmt.fmt_int(current['discharges'])} discharges "
        f"carried an estimated cost of {fmt.md_dollars(current['estimated_cost'])} "
        f"in {current_year}, with cost per discharge of "
        f"{fmt.md_dollars(current['cost_per_discharge'])} and average length of "
        f"stay of {fmt.fmt_alos(current['alos'])} days. These figures describe "
        "the data; they do not establish causes."
    )

theme.definitions_expander()
