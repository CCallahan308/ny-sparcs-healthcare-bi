# Metric definitions

Precise definitions for every KPI in the system. Implementation lands with
Milestone 2 (metrics 1-7, 9) and Milestone 3 (metric 8). Each metric gets test
coverage where practical.

Denominator rule: all shares use discharges after inclusion and exclusion
rules defined in the staging model, unless stated otherwise.

| # | Metric | Definition |
|---|---|---|
| 1 | Discharges | Count of discharge records after defined inclusion and exclusion rules |
| 2 | Cost per discharge | Sum of total estimated costs / number of discharges |
| 3 | Cost per day | Sum of total estimated costs / sum of length of stay; zero or missing LOS excluded from the denominator explicitly, never divide by zero |
| 4 | ALOS | Mean length of stay at the selected aggregation grain |
| 5 | High-severity share | Discharges with severity-of-illness 3 or 4 / all discharges, as a percentage |
| 6 | Payer exposure | Share of discharges and share of estimated costs by payer class; labeled exposure, not revenue or margin |
| 7 | ED-origin rate | Admissions originating in an emergency department / all admissions, based on the ED indicator field with documented coding assumptions |
| 8 | Facility cost index | Case-mix adjusted, APR-DRG-aware index over a selected period: per facility and APR-DRG, cost per discharge = estimated cost / discharges; statewide benchmark per DRG = median of facility-level cost per discharge among qualifying facilities (facility median, not discharge-weighted); expected benchmark cost = sum over qualifying DRGs of discharges x that DRG's median; index = total estimated cost / expected benchmark cost. The discharge mix self-weights the rollup (indirect standardization), so no separate weighting is applied. Comparisons below 30 facility-DRG discharges in the period are suppressed and counted (`suppressed_drg_comparisons`); facilities below 100 total discharges get no index and a `suppressed_low_volume` caution. Percentile ranks use average ranks among indexed facilities. Index above 1.0 is an outlier signal for investigation, not a finding of inefficiency |
| 9 | Post-acute discharge rate | Discharges to SNF, rehabilitation, or other non-home post-acute destinations / all discharges, per the documented disposition mapping |

Units and precision rules (enforced in the app):

- Currency: dollars with K / M / B scaling.
- Discharges: whole numbers.
- ALOS: one decimal.
- Percentages: one decimal point.
