# Data dictionary

## Source registry

Annual files are documented with URL, access date, row count, and observed
schema as they are ingested. Populated in Milestone 1.

| Year | URL | Access date | Rows | Schema notes |
|---|---|---|---|---|
| 2009-2024 | to be documented in Milestone 1 | | | |

Source family: Hospital Inpatient Discharges (SPARCS De-Identified), New York
State Department of Health, published on health.data.ny.gov.

## Canonical fields

Ingestion maps annual schema variations to one canonical field set. The
canonical model is finalized in Milestone 1; the intended shape:

| Canonical field | Type | Notes |
|---|---|---|
| discharge_year | int | Only temporal field; day and month are stripped by de-identification |
| facility_id / facility_name / facility_county | str | Facility identification; redacted on some records |
| age_group / gender / race / ethnicity | str | Demographics |
| length_of_stay | int | Days; explicit handling for missing or zero |
| type_of_admission | str | Emergency, elective, urgent, newborn, trauma |
| patient_disposition | str | Discharge destination, incl. post-acute mapping |
| apr_drg_code / apr_drg_description | str/int | Stable longitudinal clinical grouping key |
| apr_severity_of_illness | int | 1-4; 3-4 define high severity |
| apr_risk_of_mortality | int | 1-4 |
| apr_medical_surgical | str | Medical vs surgical classification |
| payment_typology_1/2/3 | str | Payer class; exposure analysis only |
| emergency_department_indicator | str | ED origin |
| total_charges | float | Billed charges; not reimbursement |
| total_costs | float | DOH-derived cost estimate |
| ccsr_* (recent years) / ccs_* (older years) | str | Not forced into a single longitudinal mapping |

Known source facts (verified 2026-09-01 against the 2024 dataset metadata):

- 2024 file: 2,196,737 rows, 33 columns, dataset id `sf4k-39ay`.
- Time grain is annual only (`discharge_year`); no month field exists.
- 2024 uses CCSR diagnosis/procedure categories; older years use CCS.
- Abortion-related discharges have facility and geography fields redacted.
