-- Executive trends, statewide.
-- Grain: discharge_year (one row per staged year, all facilities and payers
-- including redacted-facility records). Derived columns use NULLIF guards:
-- a zero denominator yields NULL, never an error or a fabricated zero.

CREATE OR REPLACE TABLE mart_executive_trends AS
SELECT
    discharge_year,
    COUNT(*) AS discharges,
    SUM(total_costs) AS estimated_cost,
    SUM(total_charges) AS total_charges,
    SUM(COALESCE(los_days, 0)) AS los_days_sum,
    SUM(CASE WHEN high_severity THEN 1 ELSE 0 END) AS high_severity_discharges,
    SUM(CASE WHEN ed_origin THEN 1 ELSE 0 END) AS ed_origin_discharges,
    SUM(CASE WHEN post_acute THEN 1 ELSE 0 END) AS post_acute_discharges,
    SUM(total_costs) / NULLIF(COUNT(*), 0) AS cost_per_discharge,
    SUM(total_costs) / NULLIF(SUM(COALESCE(los_days, 0)), 0) AS cost_per_day,
    SUM(COALESCE(los_days, 0)) / NULLIF(COUNT(*), 0) AS alos,
    SUM(CASE WHEN high_severity THEN 1 ELSE 0 END)::DOUBLE / NULLIF(COUNT(*), 0)
        AS high_severity_share,
    SUM(CASE WHEN ed_origin THEN 1 ELSE 0 END)::DOUBLE / NULLIF(COUNT(*), 0)
        AS ed_origin_rate,
    SUM(CASE WHEN post_acute THEN 1 ELSE 0 END)::DOUBLE / NULLIF(COUNT(*), 0)
        AS post_acute_rate
FROM stg_normalized
GROUP BY discharge_year
ORDER BY discharge_year;
