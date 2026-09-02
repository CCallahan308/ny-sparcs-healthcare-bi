-- Facility x APR-DRG benchmark detail.
-- Grain: discharge_year x facility x APR-DRG (redacted-facility records and
-- blank DRG codes excluded). Feeds the case-mix adjusted cost index in
-- src/metrics.compute_facility_benchmarks after period aggregation.

CREATE OR REPLACE TABLE mart_facility_drg_benchmarks AS
SELECT
    discharge_year,
    facility_id,
    facility_name,
    county,
    apr_drg_code,
    apr_drg_description,
    COUNT(*) AS discharges,
    SUM(total_costs) AS estimated_cost,
    SUM(COALESCE(los_days, 0)) AS los_days_sum,
    SUM(CASE WHEN high_severity THEN 1 ELSE 0 END) AS high_severity_discharges
FROM stg_normalized
WHERE NOT facility_redacted
  AND apr_drg_code IS NOT NULL
  AND TRIM(apr_drg_code) <> ''
GROUP BY
    discharge_year,
    facility_id,
    facility_name,
    county,
    apr_drg_code,
    apr_drg_description;
