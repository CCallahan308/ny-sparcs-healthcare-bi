-- Process control series.
-- Grain: metric x series x discharge_year, stored as numerator, denominator,
-- and value so control limits can be recomputed independently. Missing LOS
-- contributes zero days but stays in the denominator (documented ALOS rule);
-- data quality tracks the missing-LOS count separately.

CREATE OR REPLACE TABLE mart_process_control_series AS
WITH statewide AS (
    SELECT 'alos' AS metric, 'statewide' AS series_id, 'Statewide' AS series_label,
        discharge_year,
        SUM(COALESCE(los_days, 0)) AS numerator,
        COUNT(*) AS denominator
    FROM stg_normalized GROUP BY discharge_year
    UNION ALL
    SELECT 'cost_per_discharge', 'statewide', 'Statewide',
        discharge_year, SUM(total_costs), COUNT(*)
    FROM stg_normalized GROUP BY discharge_year
    UNION ALL
    SELECT 'post_acute_rate', 'statewide', 'Statewide',
        discharge_year, SUM(CASE WHEN post_acute THEN 1 ELSE 0 END), COUNT(*)
    FROM stg_normalized GROUP BY discharge_year
    UNION ALL
    SELECT 'high_severity_share', 'statewide', 'Statewide',
        discharge_year, SUM(CASE WHEN high_severity THEN 1 ELSE 0 END), COUNT(*)
    FROM stg_normalized GROUP BY discharge_year
    UNION ALL
    SELECT 'ed_origin_rate', 'statewide', 'Statewide',
        discharge_year, SUM(CASE WHEN ed_origin THEN 1 ELSE 0 END), COUNT(*)
    FROM stg_normalized GROUP BY discharge_year
),
by_service_line AS (
    SELECT 'alos_mdc' AS metric, 'mdc:' || mdc_code AS series_id,
        mdc_description AS series_label,
        discharge_year,
        SUM(COALESCE(los_days, 0)) AS numerator,
        COUNT(*) AS denominator
    FROM stg_normalized
    WHERE mdc_code IS NOT NULL AND TRIM(mdc_code) <> ''
    GROUP BY discharge_year, mdc_code, mdc_description
    UNION ALL
    SELECT 'cost_per_discharge_mdc', 'mdc:' || mdc_code, mdc_description,
        discharge_year,
        SUM(total_costs),
        COUNT(*)
    FROM stg_normalized
    WHERE mdc_code IS NOT NULL AND TRIM(mdc_code) <> ''
    GROUP BY discharge_year, mdc_code, mdc_description
)
SELECT
    metric,
    series_id,
    series_label,
    discharge_year,
    numerator,
    denominator,
    numerator::DOUBLE / NULLIF(denominator, 0) AS value
FROM statewide
UNION ALL
SELECT
    metric,
    series_id,
    series_label,
    discharge_year,
    numerator,
    denominator,
    numerator::DOUBLE / NULLIF(denominator, 0) AS value
FROM by_service_line;
