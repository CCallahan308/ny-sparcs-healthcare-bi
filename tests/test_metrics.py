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


# --- Facility benchmark hand calculations -----------------------------------
#
# Three facilities, two APR-DRGs, min_drg_volume=30, min_facility_volume=100.
# Qualifying cost per discharge: F1 A=10000, F1 B=10000, F2 A=12000,
# F2 B=10000, F3 B=9000 (F3 A suppressed at 20 discharges). DRG medians
# across qualifying facilities: A = median(10000, 12000) = 11000;
# B = median(10000, 10000, 9000) = 10000. Expected benchmark cost:
# F1 = 100*11000 + 40*10000 = 1,500,000; F2 = 80*11000 + 30*10000 = 1,180,000.
# Index: F1 = 1,400,000/1,500,000; F2 = 1,260,000/1,180,000.
# F3 (70 total discharges) suppressed.

import pandas as pd  # noqa: E402


def benchmark_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "facility_id": ["F1", "F1", "F2", "F2", "F3", "F3"],
            "facility_name": ["Facility One"] * 2 + ["Facility Two"] * 2 + ["Facility Three"] * 2,
            "county": ["Demo"] * 6,
            "apr_drg_code": ["A", "B", "A", "B", "A", "B"],
            "discharges": [100, 40, 80, 30, 20, 50],
            "estimated_cost": [
                1_000_000,
                400_000,
                960_000,
                300_000,
                300_000,
                450_000,
            ],
            "los_days_sum": [500, 160, 320, 90, 60, 200],
            "high_severity_discharges": [30, 8, 16, 3, 2, 10],
        }
    )


def test_cost_index_matches_hand_calculation() -> None:
    result = metrics.compute_facility_benchmarks(
        benchmark_fixture(), min_drg_volume=30, min_facility_volume=100
    )
    by_id = result.set_index("facility_id")
    assert by_id.loc["F1", "cost_index"] == pytest.approx(1_400_000 / 1_500_000)
    assert by_id.loc["F2", "cost_index"] == pytest.approx(1_260_000 / 1_180_000)
    assert by_id.loc["F1", "expected_benchmark_cost"] == pytest.approx(1_500_000)
    assert by_id.loc["F2", "expected_benchmark_cost"] == pytest.approx(1_180_000)


def test_low_volume_drg_comparisons_suppressed_and_counted() -> None:
    result = metrics.compute_facility_benchmarks(
        benchmark_fixture(), min_drg_volume=30, min_facility_volume=100
    )
    by_id = result.set_index("facility_id")
    # F3 DRG A (20 discharges) never reaches the benchmark; F3 is also below
    # the facility threshold, so its index is suppressed with a caution flag.
    assert by_id.loc["F3", "suppressed_drg_comparisons"] == 1
    assert pd.isna(by_id.loc["F3", "cost_index"])
    assert by_id.loc["F3", "status"] == "suppressed_low_volume"
    assert by_id.loc["F1", "suppressed_drg_comparisons"] == 0
    assert by_id.loc["F1", "status"] == "ok"
    assert by_id.loc["F2", "qualifying_drgs"] == 2


def test_percentile_ranks_use_average_method() -> None:
    result = metrics.compute_facility_benchmarks(
        benchmark_fixture(), min_drg_volume=30, min_facility_volume=100
    )
    by_id = result.set_index("facility_id")
    assert by_id.loc["F1", "cost_index_percentile"] == 50.0
    assert by_id.loc["F2", "cost_index_percentile"] == 100.0
    # Suppressed facility gets no percentile.
    assert pd.isna(by_id.loc["F3", "cost_index_percentile"])


def test_severity_context_carries_into_benchmarks() -> None:
    result = metrics.compute_facility_benchmarks(
        benchmark_fixture(), min_drg_volume=30, min_facility_volume=100
    )
    by_id = result.set_index("facility_id")
    # F1 qualifying discharges 140, high severity 38.
    assert by_id.loc["F1", "qualifying_discharges"] == 140
    assert by_id.loc["F1", "high_severity_share"] == pytest.approx(38 / 140)
    assert by_id.loc["F1", "alos"] == pytest.approx(660 / 140)


def test_zero_volume_rows_never_divide_by_zero() -> None:
    frame = benchmark_fixture()
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                [
                    {
                        "facility_id": "F1",
                        "facility_name": "Facility One",
                        "county": "Demo",
                        "apr_drg_code": "C",
                        "discharges": 0,
                        "estimated_cost": 0.0,
                        "los_days_sum": 0,
                        "high_severity_discharges": 0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    result = metrics.compute_facility_benchmarks(frame, min_drg_volume=30, min_facility_volume=100)
    by_id = result.set_index("facility_id")
    assert by_id.loc["F1", "cost_index"] == pytest.approx(1_400_000 / 1_500_000)
