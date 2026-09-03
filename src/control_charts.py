"""XmR control chart calculations and special-cause rule evaluation.

Method (documented fully in docs/spc_methodology.md):

- Individual values chart. Centerline = mean of baseline observations
  (assignable-cause years excluded by default, currently 2020).
- Moving range MR = |value(t) - value(t-1)| over consecutive baseline
  observations; excluded years are removed before pairing, so the range
  bridges the gap (a documented, slightly conservative choice).
- Estimated sigma = mean(MR) / 1.128, the XmR moving-range constant.
- Control limits = centerline +/- 3 sigma. Limits describe the voice of the
  process; they are never called targets.
- Signals are labeled "signal for investigation" / "potential special-cause
  variation". Nothing here supports causal claims.

Special-cause rules evaluated on the full displayed series (excluded years
included and eligible to be flagged):

- beyond_limits: a single point outside a 3-sigma control limit.
- run_of_8: eight or more consecutive points on one side of the centerline.
"""

from __future__ import annotations

from collections.abc import Mapping

from src.config import EXCLUDED_BASELINE_YEARS, SPC_BASELINE_MIN_POINTS

MR_CONSTANT = 1.128  # d2 for moving ranges of two observations
RUN_LENGTH = 8

RULE_BEYOND_LIMITS = "beyond_limits"
RULE_RUN_OF_8 = "run_of_8"


class Violation:
    """One signal for investigation on a control chart."""

    __slots__ = ("year", "rule", "value", "detail")

    def __init__(self, year: int, rule: str, value: float, detail: str) -> None:
        self.year = year
        self.rule = rule
        self.value = value
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Violation(year={self.year}, rule={self.rule}, value={self.value})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Violation):
            return NotImplemented
        return (
            self.year == other.year
            and self.rule == other.rule
            and self.value == other.value
            and self.detail == other.detail
        )


class XmRResult:
    """Limits for one series plus its signals for investigation."""

    __slots__ = (
        "center_line",
        "sigma",
        "upper_control_limit",
        "lower_control_limit",
        "baseline_years",
        "excluded_years",
        "insufficient_reason",
        "violations",
    )

    def __init__(
        self,
        center_line: float | None,
        sigma: float | None,
        upper_control_limit: float | None,
        lower_control_limit: float | None,
        baseline_years: tuple[int, ...],
        excluded_years: tuple[int, ...],
        insufficient_reason: str | None,
        violations: tuple[Violation, ...],
    ) -> None:
        self.center_line = center_line
        self.sigma = sigma
        self.upper_control_limit = upper_control_limit
        self.lower_control_limit = lower_control_limit
        self.baseline_years = baseline_years
        self.excluded_years = excluded_years
        self.insufficient_reason = insufficient_reason
        self.violations = violations

    @property
    def is_sufficient(self) -> bool:
        return self.insufficient_reason is None


def _run_violations(
    ordered_years: list[int],
    values: Mapping[int, float],
    center_line: float,
) -> list[Violation]:
    violations: list[Violation] = []
    run_side = 0  # +1 above, -1 below, consecutive count tracked separately
    run_length = 0
    for year in ordered_years:
        value = values[year]
        if value > center_line:
            side = 1
        elif value < center_line:
            side = -1
        else:
            side = 0
        if side == 0 or side != run_side:
            run_side = side
            run_length = 1 if side != 0 else 0
        else:
            run_length += 1
        if run_length >= RUN_LENGTH:
            violations.append(
                Violation(
                    year=year,
                    rule=RULE_RUN_OF_8,
                    value=value,
                    detail=(
                        f"run of {run_length} consecutive points "
                        f"{'above' if side > 0 else 'below'} centerline; "
                        "potential special-cause variation, signal for investigation"
                    ),
                )
            )
    return violations


def xmr(
    series: Mapping[int, float],
    excluded_years: frozenset[int] | set[int] = EXCLUDED_BASELINE_YEARS,
    min_baseline_points: int = SPC_BASELINE_MIN_POINTS,
    baseline_window: tuple[int, int] | None = None,
) -> XmRResult:
    """Compute XmR limits and special-cause signals for an annual series.

    `series` maps year -> value. Excluded years stay in the displayed series
    and are still evaluated against the limits; they simply do not shape the
    baseline. `baseline_window` restricts which years shape the baseline to
    an inclusive (start, end) range; limits still apply to every year. A
    window matters for strongly trending series, where a full-history
    baseline flags most years and carries little information.
    """
    ordered_years = sorted(series)
    excluded = tuple(year for year in ordered_years if year in excluded_years)
    baseline_years = tuple(
        year
        for year in ordered_years
        if year not in excluded_years
        and (baseline_window is None or baseline_window[0] <= year <= baseline_window[1])
    )
    baseline = [float(series[year]) for year in baseline_years]

    if len(baseline) < min_baseline_points:
        return XmRResult(
            center_line=None,
            sigma=None,
            upper_control_limit=None,
            lower_control_limit=None,
            baseline_years=baseline_years,
            excluded_years=excluded,
            insufficient_reason=(
                f"insufficient baseline observations: {len(baseline)} available, "
                f"{min_baseline_points} required after excluding "
                f"{sorted(excluded_years)}"
                + (
                    f" and restricting the baseline to {baseline_window[0]}-{baseline_window[1]}"
                    if baseline_window
                    else ""
                )
            ),
            violations=(),
        )

    center_line = sum(baseline) / len(baseline)
    moving_ranges = [
        abs(baseline[index] - baseline[index - 1]) for index in range(1, len(baseline))
    ]
    sigma = (sum(moving_ranges) / len(moving_ranges)) / MR_CONSTANT
    upper = center_line + 3 * sigma
    lower = center_line - 3 * sigma

    violations: list[Violation] = []
    for year in ordered_years:
        value = float(series[year])
        if value > upper:
            violations.append(
                Violation(
                    year=year,
                    rule=RULE_BEYOND_LIMITS,
                    value=value,
                    detail=(
                        f"value {value:.4g} above upper control limit "
                        f"{upper:.4g}; potential special-cause variation, "
                        "signal for investigation"
                    ),
                )
            )
        elif value < lower:
            violations.append(
                Violation(
                    year=year,
                    rule=RULE_BEYOND_LIMITS,
                    value=value,
                    detail=(
                        f"value {value:.4g} below lower control limit "
                        f"{lower:.4g}; potential special-cause variation, "
                        "signal for investigation"
                    ),
                )
            )

    violations.extend(_run_violations(ordered_years, series, center_line))
    violations.sort(key=lambda violation: (violation.year, violation.rule))

    return XmRResult(
        center_line=center_line,
        sigma=sigma,
        upper_control_limit=upper,
        lower_control_limit=lower,
        baseline_years=baseline_years,
        excluded_years=excluded,
        insufficient_reason=None,
        violations=tuple(violations),
    )
