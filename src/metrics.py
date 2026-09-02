"""KPI definitions and aggregation helpers, single source of truth.

These pure functions define the KPI semantics; the mart SQL implements the
same formulas with NULLIF guards. Tests reconcile the SQL output against
these functions. A zero or missing denominator yields None (SQL: NULL),
never a division error and never a fabricated zero.
"""

from __future__ import annotations


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
    same APR-DRG and period. Full method (weighting, suppression) lands in
    Milestone 3; the ratio itself is defined here."""
    if not statewide_median_cost_per_discharge:
        return None
    return facility_cost_per_discharge / statewide_median_cost_per_discharge
