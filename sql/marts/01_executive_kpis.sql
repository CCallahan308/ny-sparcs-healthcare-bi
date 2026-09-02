-- Executive KPI base aggregate.
-- Grain: discharge_year x facility x county x service line (APR-MDC) x payer class.
-- Measures are additive; every page-level KPI (cost per discharge, cost per
-- day, ALOS, shares) derives from these sums at whatever filter scope the
-- app applies. Denominator guards live in src/metrics.py and downstream SQL.

CREATE OR REPLACE TABLE mart_executive_kpis AS
SELECT
    discharge_year,
    facility_id,
    facility_name,
    county,
    facility_redacted,
    mdc_code,
    mdc_description,
    payer_class,
    COUNT(*) AS discharges,
    SUM(total_costs) AS estimated_cost,
    SUM(total_charges) AS total_charges,
    SUM(COALESCE(los_days, 0)) AS los_days_sum,
    SUM(CASE WHEN high_severity THEN 1 ELSE 0 END) AS high_severity_discharges,
    SUM(CASE WHEN ed_origin THEN 1 ELSE 0 END) AS ed_origin_discharges,
    SUM(CASE WHEN post_acute THEN 1 ELSE 0 END) AS post_acute_discharges,
    SUM(CASE WHEN los_capped THEN 1 ELSE 0 END) AS los_capped_discharges
FROM stg_normalized
GROUP BY
    discharge_year,
    facility_id,
    facility_name,
    county,
    facility_redacted,
    mdc_code,
    mdc_description,
    payer_class;
