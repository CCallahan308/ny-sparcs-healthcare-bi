"""Compact number formats: currency scaling, whole discharges, tight decimals."""

from __future__ import annotations


def fmt_dollars(value: float | None) -> str:
    if value is None:
        return "n/a"
    magnitude = abs(value)
    if magnitude >= 1e9:
        return f"${value / 1e9:.1f}B"
    if magnitude >= 1e6:
        return f"${value / 1e6:.1f}M"
    if magnitude >= 1e3:
        return f"${value / 1e3:.0f}K"
    return f"${value:,.0f}"


def md_dollars(value: float | None) -> str:
    """Markdown-safe currency: paired $ signs render as LaTeX math in Streamlit."""
    raw = fmt_dollars(value)
    return "n/a" if raw == "n/a" else f"\\{raw}"


def fmt_int(value: float | None) -> str:
    return "n/a" if value is None else f"{value:,.0f}"


def fmt_pct(fraction: float | None) -> str:
    return "n/a" if fraction is None else f"{fraction * 100:.1f}%"


def fmt_alos(days: float | None) -> str:
    return "n/a" if days is None else f"{days:.1f}"


def fmt_index(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def fmt_plain(value: float | None, decimals: int = 2) -> str:
    return "n/a" if value is None else f"{value:,.{decimals}f}"


def pct_delta(current: float | None, prior: float | None) -> str | None:
    """Signed period-over-period change; None when not computable."""
    if current is None or prior in (None, 0):
        return None
    return f"{(current / prior - 1) * 100:+.1f}%"
