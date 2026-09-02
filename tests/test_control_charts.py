"""XmR and special-cause rule tests against hand-calculated fixtures.

Fixture expectations were computed with independent arithmetic (not by the
module under test) on 2026-09-02.
"""

from __future__ import annotations

import pytest
from src import control_charts

# Centerline 5.0, MRbar 0.185714..., sigma 0.164640..., UCL 5.493921,
# LCL 4.506080 (independent hand calculation).
SERIES_2020_SPIKE = {
    2009: 5.0,
    2010: 5.1,
    2011: 4.9,
    2012: 5.0,
    2013: 5.2,
    2014: 4.8,
    2015: 5.1,
    2016: 5.0,
    2017: 4.9,
    2018: 5.0,
    2019: 5.1,
    2020: 8.0,
    2021: 4.9,
    2022: 5.0,
    2023: 5.2,
    2024: 4.8,
}


def test_xmr_centerline_and_limits_match_hand_calculation() -> None:
    result = control_charts.xmr(SERIES_2020_SPIKE)
    assert result.is_sufficient
    assert result.center_line == pytest.approx(5.0)
    assert result.sigma == pytest.approx(0.1857142857 / 1.128)
    assert result.upper_control_limit == pytest.approx(5.4939209726)
    assert result.lower_control_limit == pytest.approx(4.5060790274)


def test_2020_excluded_from_baseline_but_displayed_and_flagged() -> None:
    result = control_charts.xmr(SERIES_2020_SPIKE)
    assert 2020 in result.excluded_years
    assert 2020 not in result.baseline_years
    assert len(result.baseline_years) == 15
    # Including 2020 would shift the centerline to 5.2; exclusion keeps 5.0.
    assert result.center_line == pytest.approx(5.0)
    beyond_limits = [v for v in result.violations if v.rule == "beyond_limits"]
    assert [(v.year, v.rule) for v in beyond_limits] == [(2020, "beyond_limits")]


def test_exclusion_years_are_configurable() -> None:
    result = control_charts.xmr(SERIES_2020_SPIKE, excluded_years=set())
    assert result.excluded_years == ()
    assert len(result.baseline_years) == 16
    # All 16 values included: centerline becomes (75.0 + 8.0) / 16 = 5.1875.
    assert result.center_line == pytest.approx(5.1875)


def test_run_of_eight_flags_potential_special_cause() -> None:
    # CL = 5.35, 3-sigma limits roughly 4.96 to 5.74 (independent hand
    # calculation). The eight consecutive 5.6s (2013-2020) sit above the
    # centerline but inside the limits, isolating the run rule.
    years = list(range(2009, 2025))
    series = dict(zip(years, [5.0, 5.2, 5.0, 5.2] + [5.6] * 8 + [5.0, 5.2, 5.0, 5.2], strict=True))
    result = control_charts.xmr(series, excluded_years=set())
    assert result.center_line == pytest.approx(5.35)
    assert not [v for v in result.violations if v.rule == "beyond_limits"]
    run_flags = [v for v in result.violations if v.rule == "run_of_8"]
    assert run_flags, "expected at least one run-of-8 signal"
    for violation in run_flags:
        assert "signal for investigation" in violation.detail
        assert "above" in violation.detail
    # The run covers exactly 2013-2020; the 8th consecutive point is 2020.
    assert [violation.year for violation in run_flags] == [2020]


def test_insufficient_baseline_returns_reason_not_limits() -> None:
    short_series = {year: 5.0 + index * 0.1 for index, year in enumerate(range(2019, 2025))}
    result = control_charts.xmr(short_series)  # 5 baseline points after 2020 out
    assert not result.is_sufficient
    assert result.center_line is None
    assert result.upper_control_limit is None
    assert "insufficient baseline" in (result.insufficient_reason or "")
    assert result.violations == ()


def test_no_signals_on_stable_series() -> None:
    stable = dict(
        zip(
            range(2009, 2025),
            [5.0, 5.1, 4.9, 5.0, 5.2, 4.8, 5.1, 5.0, 4.9, 5.0, 5.1, 5.0, 4.9, 5.0, 5.2, 4.9],
            strict=True,
        )
    )
    result = control_charts.xmr(stable, excluded_years=set())
    assert result.violations == ()


def test_violation_language_avoids_causal_claims() -> None:
    result = control_charts.xmr(SERIES_2020_SPIKE)
    for violation in result.violations:
        assert "caused" not in violation.detail.lower()
        assert "signal for investigation" in violation.detail
