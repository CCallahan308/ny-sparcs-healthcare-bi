"""Styled Plotly builders: white ground, system font, restrained color use."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from app.components.theme import ACCENT, ALERT, FONT_STACK, GRID, MUTED, PAYER_COLORS

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.control_charts import XmRResult  # noqa: E402

pio.templates["bi"] = go.layout.Template(
    layout=go.Layout(
        font={"family": FONT_STACK, "size": 13, "color": "#2B2F2E"},
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin={"l": 10, "r": 10, "t": 24, "b": 10},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        hoverlabel={"font": {"family": FONT_STACK}},
    )
)
pio.templates.default = "bi"


def _finish(
    fig: go.Figure, y_prefix: str = "", y_pct: bool = False, x_dtick: int | None = None
) -> go.Figure:
    fig.update_layout(
        xaxis={"showgrid": False, "dtick": x_dtick},
        yaxis={
            "gridcolor": GRID,
            "tickprefix": y_prefix,
            **({"tickformat": ".0%"} if y_pct else {}),
        },
        hovermode="x unified",
        showlegend=False,
    )
    return fig


def line_chart(x, y, y_prefix: str = "", x_dtick: int | None = None) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            line={"color": ACCENT, "width": 2.5},
            marker={"size": 6},
        )
    )
    return _finish(fig, y_prefix=y_prefix, x_dtick=x_dtick)


def stacked_share_bar(
    pivot: pd.DataFrame, colors: Mapping[str, str] | None = None, x_dtick: int | None = None
) -> go.Figure:
    palette = colors or PAYER_COLORS
    fig = go.Figure()
    for column in pivot.columns:
        fig.add_trace(
            go.Bar(
                x=pivot.index,
                y=pivot[column],
                name=str(column),
                marker_color=palette.get(str(column), MUTED),
            )
        )
    fig.update_layout(barmode="stack")
    finished = _finish(fig, y_pct=True, x_dtick=x_dtick)
    # Single-series stacks (one share column) need no legend; payer mixes do.
    finished.update_layout(showlegend=len(pivot.columns) > 1)
    return finished


def grouped_share_bars(categories, series: dict[str, list], colors: Mapping[str, str]) -> go.Figure:
    fig = go.Figure()
    for name, values in series.items():
        fig.add_trace(
            go.Bar(
                x=categories,
                y=values,
                name=name,
                marker_color=colors[name],
            )
        )
    tallest = max(max(values) for values in series.values())
    fig.update_layout(
        barmode="group",
        showlegend=True,
        # Headroom so the top tick and bar labels never clip.
        yaxis={"range": [0, min(1.0, tallest * 1.15)]},
    )
    return _finish(fig, y_pct=True)


def horizontal_stacked_share(
    pivot: pd.DataFrame, colors: Mapping[str, str] | None = None
) -> go.Figure:
    """Row-per-category stacked shares; readable for long DRG labels."""
    palette = colors or PAYER_COLORS
    fig = go.Figure()
    for column in pivot.columns:
        fig.add_trace(
            go.Bar(
                y=pivot.index,
                x=pivot[column],
                name=str(column),
                orientation="h",
                marker_color=palette.get(str(column), MUTED),
            )
        )
    fig.update_layout(
        barmode="stack",
        showlegend=len(pivot.columns) > 1,
        height=max(360, 34 * len(pivot.index) + 90),
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        xaxis={"tickformat": ".0%", "gridcolor": GRID},
        yaxis={"autorange": "reversed", "showgrid": False},
        hovermode="y unified",
    )
    return fig


def horizontal_ranked_bar(labels, values, y_prefix: str = "") -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=ACCENT,
        )
    )
    fig.update_layout(
        xaxis={"gridcolor": GRID, "tickprefix": y_prefix, "title": None},
        yaxis={"title": None},
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
    )
    return fig


def bubble_scatter(
    x,
    y,
    size,
    text,
    median_x: float,
    median_y: float,
    x_title: str,
    y_title: str,
) -> go.Figure:
    sizeref = 2.0 * max(size) / (55**2)
    fig = go.Figure(
        go.Scatter(
            x=x,
            y=y,
            mode="markers",
            marker={
                "size": size,
                "sizeref": sizeref,
                "sizemin": 6,
                "color": ACCENT,
                "opacity": 0.75,
                "line": {"width": 0.5, "color": "white"},
            },
            text=text,
            hovertemplate="%{text}<br>"
            + x_title
            + ": %{x:.1f}<br>"
            + y_title
            + ": %{y:,.0f}<extra></extra>",
            showlegend=False,
        )
    )
    fig.add_vline(
        x=median_x,
        line={"dash": "dash", "color": MUTED},
        annotation_text="statewide median",
        annotation_font_color=MUTED,
    )
    fig.add_hline(
        y=median_y,
        line={"dash": "dash", "color": MUTED},
        annotation_text="statewide median",
        annotation_font_color=MUTED,
        annotation_position="right",
    )
    fig.update_layout(
        xaxis={"title": x_title, "gridcolor": GRID},
        yaxis={"title": y_title, "gridcolor": GRID, "tickprefix": "$"},
    )
    return fig


def control_chart(
    series: Mapping[int, float],
    result: XmRResult,
    y_prefix: str = "",
    x_dtick: int = 2,
) -> go.Figure:
    years = sorted(series)
    fig = go.Figure(
        go.Scatter(
            x=years,
            y=[series[year] for year in years],
            mode="lines+markers",
            line={"color": ACCENT, "width": 2.5},
            marker={"size": 7},
            showlegend=False,
        )
    )
    if result.upper_control_limit is not None:
        for value, label, color in [
            (result.center_line, "Centerline (baseline mean)", MUTED),
            (result.upper_control_limit, "Upper control limit", ALERT),
            (result.lower_control_limit, "Lower control limit", ALERT),
        ]:
            fig.add_hline(
                y=value,
                line={"dash": "dash", "color": color, "width": 1.2},
                annotation_text=f"{label}: {y_prefix}{value:,.2f}",
                annotation_font_color=color,
                annotation_position="right",
            )
    for year in result.excluded_years:
        fig.add_vrect(
            x0=year - 0.5,
            x1=year + 0.5,
            fillcolor="#F1F3F2",
            line_width=0,
            annotation_text=f"{year} excluded from baseline",
            annotation_font_color=MUTED,
        )
    return _finish(fig, y_prefix=y_prefix, x_dtick=x_dtick)
