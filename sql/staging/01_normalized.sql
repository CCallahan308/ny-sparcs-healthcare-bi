-- Normalized staging model.
-- Grain: one row per source discharge record (unchanged from stg_discharges).
-- Adds normalized flags and mappings derived from verified value domains
-- (docs/data_dictionary.md, "Verified value-domain findings", 2026-09-02):
--   payer_class   : harmonizes "Source of Payment" era (2009-2016) and
--                   "Payment Typology" era (2017+) payer taxonomies
--   post_acute    : documented SNF / rehab / LTC / hospice / custodial mapping
--   ed_origin     : Y/N emergency department indicator as boolean
--   severity_code : numeric severity 0-4; NULL when word-form or blank
--   facility_redacted : blank facility fields (source redactions)
-- Any payer value outside the explicit map lands in 'Other' and is reported
-- per year in run metadata, never silently dropped.

CREATE OR REPLACE TABLE stg_normalized AS
SELECT
    d.source_year,
    d.source_file,
    d.discharge_year,
    d.facility_id,
    d.facility_name,
    d.hospital_county AS county,
    (TRIM(COALESCE(d.facility_id, '')) = '') AS facility_redacted,
    TRIM(d.apr_mdc_code) AS mdc_code,
    TRIM(d.apr_mdc_description) AS mdc_description,
    TRIM(d.apr_drg_code) AS apr_drg_code,
    TRIM(d.apr_drg_description) AS apr_drg_description,
    TRY_CAST(d.apr_severity_of_illness AS INTEGER) AS severity_code,
    (TRY_CAST(d.apr_severity_of_illness AS INTEGER) >= 3) AS high_severity,
    d.length_of_stay AS los_days,
    d.los_capped,
    (d.emergency_department_indicator = 'Y') AS ed_origin,
    TRIM(d.type_of_admission) AS admission_type,
    TRIM(d.patient_disposition) AS disposition_raw,
    TRIM(d.patient_disposition) IN (
        'Skilled Nursing Home',
        'Inpatient Rehabilitation Facility',
        'Medicare Cert Long Term Care Hospital',
        'Hosp Basd Medicare Approved Swing Bed',
        'Medicaid Cert Nursing Facility',
        'Facility w/ Custodial/Supportive Care',
        'Hospice - Medical Facility',
        'Hospice - Home'
    ) AS post_acute,
    TRIM(d.payment_typology_1) AS payer_raw,
    CASE
        WHEN TRIM(COALESCE(d.payment_typology_1, '')) = '' THEN 'Unknown'
        WHEN TRIM(d.payment_typology_1) = 'Medicare' THEN 'Medicare'
        WHEN TRIM(d.payment_typology_1) = 'Medicaid' THEN 'Medicaid'
        WHEN TRIM(d.payment_typology_1) IN (
            'Private Health Insurance',
            'Blue Cross',
            'Blue Cross/Blue Shield',
            'Insurance Company'
        ) THEN 'Private'
        WHEN TRIM(d.payment_typology_1) = 'Managed Care, Unspecified' THEN 'Managed Care'
        WHEN TRIM(d.payment_typology_1) = 'Self-Pay' THEN 'Self-Pay'
        WHEN TRIM(d.payment_typology_1) IN (
            'Federal/State/Local/VA',
            'CHAMPUS',
            'Other Federal Program'
        ) THEN 'Other Government'
        ELSE 'Other'
    END AS payer_class,
    d.total_charges,
    d.total_costs,
    CASE
        WHEN d.ccsr_diagnosis_code IS NOT NULL THEN 'CCSR'
        WHEN d.ccs_diagnosis_code IS NOT NULL THEN 'CCS'
        ELSE 'NONE'
    END AS clinical_grouping
FROM stg_discharges d;
