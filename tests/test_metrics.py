"""KPI calculation tests: formulas and zero-denominator behavior."""

from __future__ import annotations

import pytest
from src import metrics


def test_cost_per_discharge() -> None:
    assert metrics.cost_per_discharge(1_000_000.0, 400) == 2_500.0
    assert metrics.cost_per_discharge(0.0, 400) == 0.0


def test_cost_per_day_guards_zero_and_negative_denominator() -> None:
    assert metrics.cost_per_day(1_000_000.0, 0) is None
    assert metrics.cost_per_day(1_000_000.0, -5) is None
    assert metrics.cost_per_day(1_000_000.0, 2_000) == 500.0


def test_alos_guards_zero_denominator() -> None:
    assert metrics.alos(1_200, 300) == 4.0
    assert metrics.alos(1_200, 0) is None


def test_share_functions_guard_zero_denominator() -> None:
    for function in (
        metrics.high_severity_share,
        metrics.ed_origin_rate,
        metrics.post_acute_rate,
        metrics.exposure_share,
    ):
        assert function(50, 200) == pytest.approx(0.25)
        assert function(50, 0) is None


def test_facility_cost_index() -> None:
    assert metrics.facility_cost_index(12_000.0, 10_000.0) == pytest.approx(1.2)
    assert metrics.facility_cost_index(12_000.0, 0.0) is None


def test_discharges_is_documented_count() -> None:
    assert metrics.discharges(37_800_000) == 37_800_000
