# Statistical process control methodology

How this system draws control limits and flags signals, and what those
signals do and do not mean.

## XmR charts on annual observations

- **Individual values.** Each series is one observation per year
  (source grain is annual; the de-identified data carries no finer timing).
- **Centerline** CL = mean of baseline observations.
- **Moving range** MR = |value(t) - value(t-1)| over consecutive baseline
  observations. Excluded years are removed before pairing, so a range
  bridges the gap (for example 2019 to 2021). This slightly widens the
  estimated sigma and is a documented, conservative choice.
- **Estimated sigma** = mean(MR) / 1.128, the control-chart constant for
  moving ranges of two.
- **Control limits** = CL +/- 3 sigma. Limits describe the voice of the
  process. They are never called targets and carry no performance judgment.
- **Insufficient data.** Fewer than six baseline observations yields no
  limits and no signals, with the reason stated (`SPC_BASELINE_MIN_POINTS`).

## Baseline exclusion of 2020

2020 is an assignable-cause period (pandemic response). By default it is
excluded from the baseline (centerline, moving ranges, sigma, limits) while
remaining in the displayed series and remaining eligible to be flagged. The
exclusion set is configuration (`EXCLUDED_BASELINE_YEARS`), not hidden logic,
and the app annotates excluded years on the chart.

## Special-cause rules

Evaluated on the full displayed series, excluded years included:

| Rule | Definition | Language used |
|---|---|---|
| `beyond_limits` | A single point outside a 3-sigma control limit | "potential special-cause variation, signal for investigation" |
| `run_of_8` | Eight or more consecutive points on one side of the centerline | same |

## What signals mean here

A signal is a signal for investigation. Nothing in a control-chart signal
identifies a cause, and this system makes no causal claims anywhere: not in
code, documentation, or interface text. With roughly sixteen annual
observations, limits are estimates with real uncertainty; borderline signals
deserve correspondingly cautious reading.

## Where limits are computed

`src/control_charts.py` (`xmr`) is the single implementation, unit-tested
against hand-calculated fixtures in `tests/test_control_charts.py`. The
Process Control page computes limits in-app from
`process_control_series.parquet` using this module, so the chart, the
violation table, and the tests all share one definition.
