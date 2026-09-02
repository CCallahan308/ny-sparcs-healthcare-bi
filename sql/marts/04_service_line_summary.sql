-- Service line summary.
-- Grain: discharge_year x service line (APR-MDC) x APR-DRG.
-- APR-DRG is the stable longitudinal clinical grouping key; MDC carries the
-- service-line rollup. CCS and CCSR categories are never mixed into this
-- grain (they exist only in staging for documentation).

CREATE OR REPLACE TABLE mart_service_line_summary AS
SELECT
    discharge_year,
    mdc_code,
    mdc_description,
    apr_drg_code,
    apr_drg_description,
    COUNT(*) AS discharges,
    SUM(total_costs) AS estimated_cost,
    SUM(COALESCE(los_days, 0)) AS los_days_sum,
    SUM(CASE WHEN high_severity THEN 1 ELSE 0 END) AS high_severity_discharges,
    SUM(total_costs) / NULLIF(COUNT(*), 0) AS cost_per_discharge,
    SUM(COALESCE(los_days, 0))::DOUBLE / NULLIF(COUNT(*), 0) AS alos
FROM stg_normalized
GROUP BY
    discharge_year,
    mdc_code,
    mdc_description,
    apr_drg_code,
    apr_drg_description;
