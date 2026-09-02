-- Facility benchmarks, base aggregates.
-- Grain: discharge_year x facility (redacted-facility records excluded; they
-- carry no comparable facility identity).
-- Milestone 3 layers the APR-DRG-aware cost index, percentile ranks, and
-- low-volume suppression on top of this mart.

CREATE OR REPLACE TABLE mart_facility_benchmarks AS
SELECT
    discharge_year,
    facility_id,
    facility_name,
    county,
    COUNT(*) AS discharges,
    SUM(total_costs) AS estimated_cost,
    SUM(COALESCE(los_days, 0)) AS los_days_sum,
    SUM(CASE WHEN high_severity THEN 1 ELSE 0 END) AS high_severity_discharges,
    SUM(total_costs) / NULLIF(COUNT(*), 0) AS cost_per_discharge,
    SUM(COALESCE(los_days, 0))::DOUBLE / NULLIF(COUNT(*), 0) AS alos,
    SUM(CASE WHEN high_severity THEN 1 ELSE 0 END)::DOUBLE / NULLIF(COUNT(*), 0)
        AS high_severity_share
FROM stg_normalized
WHERE NOT facility_redacted
GROUP BY
    discharge_year,
    facility_id,
    facility_name,
    county;
