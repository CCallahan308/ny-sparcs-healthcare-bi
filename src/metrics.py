"""KPI definitions and aggregation helpers, single source of truth.

These pure functions define the KPI semantics; the mart SQL implements the
same formulas with NULLIF guards. Tests reconcile the SQL output against
these functions. A zero or missing denominator yields None (SQL: NULL),
never a division error and never a fabricated zero.
"""

from __future__ import annotations

import pandas as pd


def discharges(count: int) -> int:
    """Count of discharge records after inclusion and exclusion rules."""
    return int(count)


def cost_per_discharge(total_estimated_cost: float, discharge_count: int) -> float | None:
    """Sum of estimated costs divided by number of discharges."""
    if not discharge_count:
        return None
    return total_estimated_cost / discharge_count


def cost_per_day(total_estimated_cost: float, los_days: int) -> float | None:
    """Sum of estimated costs divided by sum of length of stay.

    Zero, missing, or negative bed-day totals have no defined cost per day;
    the guard returns None instead of dividing by zero.
    """
    if not los_days or los_days <= 0:
        return None
    return total_estimated_cost / los_days


def alos(los_days: int, discharge_count: int) -> float | None:
    """Mean length of stay at the selected aggregation grain."""
    if not discharge_count:
        return None
    return los_days / discharge_count


def high_severity_share(high_severity_discharges: int, discharge_count: int) -> float | None:
    """Share of discharges with severity-of-illness 3 or 4."""
    if not discharge_count:
        return None
    return high_severity_discharges / discharge_count


def ed_origin_rate(ed_origin_discharges: int, discharge_count: int) -> float | None:
    """Share of admissions that originated in an emergency department."""
    if not discharge_count:
        return None
    return ed_origin_discharges / discharge_count


def post_acute_rate(post_acute_discharges: int, discharge_count: int) -> float | None:
    """Share of discharges to SNF, rehabilitation, or other post-acute destinations."""
    if not discharge_count:
        return None
    return post_acute_discharges / discharge_count


def exposure_share(part: float, whole: float) -> float | None:
    """Payer exposure: share of discharges or estimated cost.

    Exposure only; this is not revenue or margin.
    """
    if not whole:
        return None
    return part / whole


def facility_cost_index(
    facility_cost_per_discharge: float, statewide_median_cost_per_discharge: float
) -> float | None:
    """Facility cost per discharge relative to the statewide median for the
    same APR-DRG and period."""
    if not statewide_median_cost_per_discharge:
        return None
    return facility_cost_per_discharge / statewide_median_cost_per_discharge


# --- Facility benchmark method ---------------------------------------------
#
# Case-mix adjusted cost index, computed from facility-by-APR-DRG aggregates
# over a selected period:
#
# 1. Per facility and APR-DRG: cost per discharge = estimated cost /
#    discharges (period-aggregated sums).
# 2. Statewide benchmark per APR-DRG = median of facility-level cost per
#    discharge among qualifying facilities (facility-level median, not
#    discharge-weighted, so one large facility cannot define the benchmark).
# 3. Qualifying comparisons: facility-DRG volume >= min_drg_volume in the
#    period. Non-qualifying comparisons are suppressed and counted, never
#    silently dropped.
# 4. Facility expected benchmark cost = sum over qualifying DRGs of
#    discharges x statewide median cost per discharge for that DRG.
# 5. Cost index = total estimated cost / expected benchmark cost. This is an
#    indirect-standardization ratio: the discharge mix self-weights the
#    rollup, so no separate weighting scheme is applied.
# 6. Facilities below min_facility_volume total discharges in the period get
#    no index (suppressed) and a caution flag.
# 7. Percentile ranks use average ranks among facilities with an index.
#
# Index above 1.0 means higher estimated cost per discharge than the
# median-rate benchmark for the same case mix: an outlier signal for
# investigation, not a finding of inefficiency.


def compute_facility_benchmarks(
    facility_drg: pd.DataFrame,
    min_drg_volume: int | None = None,
    min_facility_volume: int | None = None,
) -> pd.DataFrame:
    """Compute the case-mix adjusted facility cost index for one period.

    `facility_drg` columns: facility_id, facility_name, county,
    apr_drg_code, discharges, estimated_cost, los_days_sum,
    high_severity_discharges (aggregated over the selected period).
    """
    from src.config import MIN_DRG_VOLUME_PER_PERIOD, MIN_FACILITY_VOLUME_PER_PERIOD

    if min_drg_volume is None:
        min_drg_volume = MIN_DRG_VOLUME_PER_PERIOD
    if min_facility_volume is None:
        min_facility_volume = MIN_FACILITY_VOLUME_PER_PERIOD

    frame = facility_drg.copy()
    frame = frame[frame["discharges"] > 0]
    frame["cost_per_discharge"] = frame["estimated_cost"] / frame["discharges"]

    qualifying = frame[frame["discharges"] >= min_drg_volume].copy()
    medians = (
        qualifying.groupby("apr_drg_code")["cost_per_discharge"]
        .median()
        .rename("statewide_median_cpd")
    )
    qualifying = qualifying.merge(medians, on="apr_drg_code", how="left")
    qualifying["expected_cost"] = qualifying["discharges"] * qualifying["statewide_median_cpd"]

    grouped = qualifying.groupby("facility_id", as_index=False).agg(
        facility_name=("facility_name", "first"),
        county=("county", "first"),
        qualifying_drgs=("apr_drg_code", "nunique"),
        qualifying_discharges=("discharges", "sum"),
        estimated_cost=("estimated_cost", "sum"),
        expected_benchmark_cost=("expected_cost", "sum"),
        los_days_sum=("los_days_sum", "sum"),
        high_severity_discharges=("high_severity_discharges", "sum"),
    )

    totals = frame.groupby("facility_id").agg(total_discharges=("discharges", "sum"))
    suppressed = (
        (frame["discharges"] < min_drg_volume)
        .groupby(frame["facility_id"])
        .sum()
        .rename("suppressed_drg_comparisons")
    )
    grouped = grouped.merge(totals, on="facility_id").merge(suppressed, on="facility_id")

    grouped["cost_index"] = grouped.apply(
        lambda row: exposure_share(row["estimated_cost"], row["expected_benchmark_cost"]),
        axis=1,
    )
    low_volume = grouped["total_discharges"] < min_facility_volume
    grouped.loc[low_volume, "cost_index"] = None
    grouped["status"] = ["suppressed_low_volume" if flag else "ok" for flag in low_volume]
    grouped["alos"] = grouped.apply(
        lambda row: alos(row["los_days_sum"], row["qualifying_discharges"]), axis=1
    )
    grouped["high_severity_share"] = grouped.apply(
        lambda row: high_severity_share(
            row["high_severity_discharges"], row["qualifying_discharges"]
        ),
        axis=1,
    )
    grouped["cost_index_percentile"] = percentile_ranks(grouped["cost_index"])

    return grouped[
        [
            "facility_id",
            "facility_name",
            "county",
            "total_discharges",
            "qualifying_discharges",
            "qualifying_drgs",
            "suppressed_drg_comparisons",
            "estimated_cost",
            "expected_benchmark_cost",
            "cost_index",
            "cost_index_percentile",
            "alos",
            "high_severity_share",
            "status",
        ]
    ]


def percentile_ranks(values: pd.DataFrame) -> pd.DataFrame:
    """Percentile rank (0-100, average-rank method) among non-null values.

    Nulls stay null; a value's percentile is the share of ranked values at
    or below it, using average ranks for ties.
    """
    return (values.rank(method="average", pct=True, na_option="keep") * 100).round(1)
