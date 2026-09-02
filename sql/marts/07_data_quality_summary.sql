-- Data quality summary.
-- Grain: discharge_year. Completeness rates are fractions of rows with a
-- usable value per core field; invalid-value counts flag negatives that
-- downstream checks reject in aggregates.

CREATE OR REPLACE TABLE mart_data_quality_summary AS
SELECT
    discharge_year AS year,
    ANY_VALUE(source_file) AS source_file,
    COUNT(*) AS rows,
    COUNT(DISTINCT facility_id) FILTER (WHERE NOT facility_redacted)
        AS distinct_facilities,
    COUNT(DISTINCT apr_drg_code) AS distinct_apr_drgs,
    AVG(CAST(facility_redacted AS INT)) AS facility_redacted_share,
    AVG(CAST(apr_drg_code IS NULL OR TRIM(COALESCE(apr_drg_code, '')) = '' AS INT))
        AS apr_drg_missing_share,
    AVG(CAST(severity_code IS NULL AS INT)) AS severity_missing_share,
    AVG(CAST(los_days IS NULL AS INT)) AS los_missing_share,
    AVG(CAST(ed_origin IS NULL AS INT)) AS ed_indicator_missing_share,
    AVG(CAST(payer_class = 'Unknown' AS INT)) AS payer_unknown_share,
    AVG(CAST(disposition_raw IS NULL OR TRIM(COALESCE(disposition_raw, '')) = '' AS INT))
        AS disposition_missing_share,
    AVG(CAST(total_charges IS NULL AS INT)) AS charges_missing_share,
    AVG(CAST(total_costs IS NULL AS INT)) AS costs_missing_share,
    COUNT(*) FILTER (WHERE total_charges < 0) AS negative_charges,
    COUNT(*) FILTER (WHERE total_costs < 0) AS negative_costs,
    COUNT(*) FILTER (WHERE los_days < 0) AS negative_los,
    SUM(CAST(los_capped AS INT)) AS los_capped,
    ANY_VALUE(clinical_grouping) AS clinical_grouping
FROM stg_normalized
GROUP BY discharge_year
ORDER BY discharge_year;
