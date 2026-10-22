"""Payer Exposure: concentration of discharges and estimated cost by payer."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.components import charts, data, filters, theme  # noqa: E402

st.set_page_config(page_title="Payer Exposure", layout="centered")
theme.apply_theme()

payer = data.load_mart("payer_exposure.parquet")
theme.page_header(
    "Payer exposure",
    "How are discharges and estimated cost distributed across payer classes?",
    "Payer classes harmonize the 2009-2016 and 2017+ source taxonomies "
    "(documented in the data dictionary).",
    mart_name="payer_exposure.parquet",
)

with st.sidebar:
    st.markdown("#### Filters")
    bounds = filters.year_range(
        payer, include_all_years=data.is_demo_mart("payer_exposure.parquet")
    )
    counties = filters.multiselect(payer, "county", "County")
    facilities = filters.multiselect(payer, "facility_name", "Facility")

scope = filters.apply(payer, year_bounds=bounds, counties=counties, facilities=facilities)

if scope.empty:
    st.info(
        "No discharges match the selected filters. Widen the year range or "
        "clear the county or facility filter."
    )
    st.stop()

st.markdown("#### Payer mix by year: share of discharges")
mix = scope.pivot_table(
    index="discharge_year", columns="payer_class", values="discharges", aggfunc="sum"
).fillna(0)
mix_share = mix.div(mix.sum(axis=1), axis=0)
st.plotly_chart(charts.stacked_share_bar(mix_share, x_dtick=2), width="stretch", key="payer_mix")
st.caption(
    "Grain: payer class x year, selected scope. Denominator: all discharges "
    "in the year. Blank or unmapped source payers appear as Unknown or Other "
    "per the documented mapping."
)

current_year = int(scope["discharge_year"].max())
latest = scope[scope["discharge_year"] == current_year]
by_payer = (
    latest.groupby("payer_class")
    .agg(discharges=("discharges", "sum"), estimated_cost=("estimated_cost", "sum"))
    .sort_values("discharges", ascending=False)
    .reset_index()
)
by_payer["discharge_share"] = by_payer["discharges"] / by_payer["discharges"].sum()
by_payer["cost_share"] = by_payer["estimated_cost"] / by_payer["estimated_cost"].sum()

st.markdown(f"#### Payer shares, {current_year}")
col_left, col_right = st.columns(2)
with col_left:
    st.markdown("Share of discharges")
    st.plotly_chart(
        charts.stacked_share_bar(
            by_payer.set_index("payer_class")[["discharge_share"]].rename(
                columns={"discharge_share": "share"}
            ),
            colors={"share": "#4C9A8E"},
        ),
        width="stretch",
        key="payer_discharge_share",
    )
with col_right:
    st.markdown("Share of estimated cost")
    st.plotly_chart(
        charts.stacked_share_bar(
            by_payer.set_index("payer_class")[["cost_share"]].rename(
                columns={"cost_share": "share"}
            ),
            colors={"share": "#0F6E63"},
        ),
        width="stretch",
        key="payer_cost_share",
    )
st.caption(
    "Two views of the same year. Where the cost share exceeds the discharge "
    "share, the class's cases are more resource-intensive on average; this "
    "describes the data rather than explaining it."
)

st.markdown("#### Facility breakdown, latest year")
facility = (
    latest.groupby(["facility_name", "county", "payer_class"])
    .agg(discharges=("discharges", "sum"), estimated_cost=("estimated_cost", "sum"))
    .reset_index()
)
facility["payer_share"] = facility.groupby("facility_name")["discharges"].transform(
    lambda values: values / values.sum()
)
table = facility.pivot_table(
    index=["facility_name", "county"], columns="payer_class", values="payer_share"
).fillna(0)
st.dataframe(
    table,
    column_config={
        payer_class: st.column_config.NumberColumn(payer_class, format=".1%")
        for payer_class in table.columns
    },
    width="stretch",
    height=380,
)
data.download_button(
    table.reset_index(), "payer_by_facility.csv", "Download facility payer mix (CSV)"
)

st.warning(
    "Limitation: payer analysis here is exposure, not reimbursement, net "
    "revenue, or margin. The public source contains no payment amounts."
)

theme.definitions_expander()
