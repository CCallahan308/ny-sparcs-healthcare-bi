"""Process Control: annual XmR charts and signals for investigation."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.components import charts, data, theme  # noqa: E402
from app.components import formatting as fmt  # noqa: E402
from src import control_charts  # noqa: E402

st.set_page_config(page_title="Process Control", layout="centered")
theme.apply_theme()

series_mart = data.load_mart("process_control_series.parquet")
theme.page_header(
    "Process control",
    "Which annual metrics show signals rather than routine variation?",
    "XmR charts on annual observations. Baselines exclude assignable-cause "
    "years (2020 by default); excluded years stay visible and can be flagged.",
)

METRIC_LABELS = {
    "alos": "Statewide average length of stay (days)",
    "cost_per_discharge": "Statewide estimated cost per discharge",
    "post_acute_rate": "Statewide post-acute discharge rate",
    "high_severity_share": "Statewide high-severity share",
    "ed_origin_rate": "Statewide ED-origin rate",
    "alos_mdc": "Average length of stay by service line (days)",
    "cost_per_discharge_mdc": "Estimated cost per discharge by service line",
}

statewide_metrics = [
    metric
    for metric in [
        "alos",
        "cost_per_discharge",
        "post_acute_rate",
        "high_severity_share",
        "ed_origin_rate",
    ]
    if metric in set(series_mart["metric"])
]
mdc_metrics = [
    metric
    for metric in ["alos_mdc", "cost_per_discharge_mdc"]
    if metric in set(series_mart["metric"])
]

with st.sidebar:
    st.markdown("#### Series")
    metric = st.selectbox(
        "Metric",
        statewide_metrics + mdc_metrics,
        format_func=METRIC_LABELS.__getitem__,
    )
    series_id = "statewide"
    series_label = "Statewide"
    if metric in mdc_metrics:
        options = (
            series_mart[series_mart["metric"] == metric]
            .groupby("series_id")["series_label"]
            .first()
            .sort_values()
        )
        series_id = st.selectbox(
            "Service line", options.index.tolist(), format_func=lambda sid: options[sid]
        )
        series_label = options[series_id]

subset = series_mart[(series_mart["metric"] == metric) & (series_mart["series_id"] == series_id)]
annual: dict[int, float] = {
    int(row.discharge_year): float(row.value) for row in subset.itertuples() if pd.notna(row.value)
}

if not annual:
    st.info("The selected series has no observations in the current marts.")
    st.stop()

st.markdown(f"#### {METRIC_LABELS[metric]}: {series_label}")
result = control_charts.xmr(annual)
prefix = "$" if "cost" in metric else ""

st.plotly_chart(
    charts.control_chart(annual, result, y_prefix=prefix),
    width="stretch",
    key="control_chart",
)

if not result.is_sufficient:
    st.warning(result.insufficient_reason)
    st.caption(
        "Control limits are not computed with too few baseline observations; "
        "the series is still shown for context."
    )
else:
    st.caption(
        f"Centerline {prefix}{result.center_line:,.2f} from "
        f"{len(result.baseline_years)} baseline years; sigma estimated from "
        "the mean moving range / 1.128; limits at +/- 3 sigma. Shaded year(s) "
        "are excluded from the baseline and annotated on the chart."
    )

    rows = []
    for violation in result.violations:
        limit = None
        if result.upper_control_limit is not None and violation.value > result.upper_control_limit:
            limit = result.upper_control_limit
        elif (
            result.lower_control_limit is not None and violation.value < result.lower_control_limit
        ):
            limit = result.lower_control_limit
        rows.append(
            {
                "Year": violation.year,
                "Metric": METRIC_LABELS[metric],
                "Series": series_label,
                "Rule": violation.rule,
                "Observed": fmt.fmt_plain(violation.value),
                "Control limit": fmt.fmt_plain(limit) if limit is not None else "centerline rule",
                "Reading": "signal for investigation; potential special-cause variation",
            }
        )
    st.markdown("##### Signals for investigation")
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.write("No points beyond control limits and no 8-point runs in this series.")

with st.expander("Methodology"):
    st.markdown(
        "- Centerline CL = mean of baseline years (2020 excluded by default).\n"
        "- Moving range MR = |value(t) - value(t-1)| over consecutive baseline "
        "years; excluded years are removed before pairing, so ranges bridge "
        "the gap (a documented, slightly conservative choice).\n"
        "- Estimated sigma = mean(MR) / 1.128 (XmR constant).\n"
        "- Limits: CL +/- 3 sigma. These are voice-of-the-process limits, "
        "never targets.\n"
        "- Rules: a point beyond a 3-sigma limit (`beyond_limits`) and a run "
        "of 8 consecutive points on one side of the centerline (`run_of_8`).\n"
        "- With roughly sixteen annual observations, limits are estimates "
        "with real uncertainty; treat borderline signals cautiously. Full "
        "method: docs/spc_methodology.md."
    )

theme.definitions_expander()
