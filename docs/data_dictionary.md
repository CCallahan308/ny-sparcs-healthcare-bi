# Data dictionary

## Source registry

All 16 annual files live on health.data.ny.gov, discovered and verified
2026-09-02 by `scripts/inspect_sources.py`. Machine-readable copy:
`src/sources.toml` and `docs/schema_report.json`.

| Year | Dataset ID | Rows | Grouping | Notes |
|---|---|---|---|---|
| 2009 | [q6hk-esrj](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/q6hk-esrj) | 2,665,414 | CCS | "Source of Payment" payer era |
| 2010 | [mtfm-rxf4](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/mtfm-rxf4) | 2,622,133 | CCS | |
| 2011 | [pyhr-5eas](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/pyhr-5eas) | 2,589,121 | CCS | Outlier schema, see below |
| 2012 | [u4ud-w55t](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/u4ud-w55t) | 2,544,543 | CCS | |
| 2013 | [npsr-cm47](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/npsr-cm47) | 2,428,905 | CCS | |
| 2014 | [rmwa-zns4](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/rmwa-zns4) | 2,367,550 | CCS | |
| 2015 | [82xm-y6g8](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/82xm-y6g8) | 2,346,931 | CCS | |
| 2016 | [gnzp-ekau](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/gnzp-ekau) | 2,343,429 | CCS | Last Source-of-Payment year |
| 2017 | [22g3-z7e7](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/22g3-z7e7) | 2,343,569 | CCS | First Payment-Typology year |
| 2018 | [yjgt-tq93](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/yjgt-tq93) | 2,352,807 | CCSR | First CCSR year |
| 2019 | [4ny4-j5zv](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/4ny4-j5zv) | 2,339,462 | CCSR | |
| 2020 | [nxi5-zj9x](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/nxi5-zj9x) | 2,052,408 | CCSR | Assignable-cause year |
| 2021 | [tg3i-cinn](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/tg3i-cinn) | 2,135,260 | CCSR | |
| 2022 | [5dtw-tffi](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/5dtw-tffi) | 2,103,433 | CCSR | |
| 2023 | [46xm-urtu](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/46xm-urtu) | 2,125,754 | CCSR | |
| 2024 | [sf4k-39ay](https://health.data.ny.gov/Health/Hospital-Inpatient-Discharges-SPARCS-De-Identified/sf4k-39ay) | 2,196,737 | CCSR | |

Total: approximately 37.8 million discharge records.

### Verified value-domain findings (50,000-row samples, 2026-09-02)

- Payer taxonomy drifts across eras: 2009 uses "Insurance Company" and
  "Blue Cross"; later years use "Private Health Insurance" and
  "Blue Cross/Blue Shield". Cross-year payer harmonization happens in the
  marts layer with a documented mapping.
- APR severity of illness holds numeric codes 0-4 in staged years; 0 denotes
  unclassified severity.
- APR risk of mortality holds word forms ("Minor" ... "Extreme", plus
  "Undetermined" in 2024), not codes.
- Length of stay arrives capped as the literal string "120 +"; staged as 120
  with `los_capped = true`.
- 2011 deviations: "Age" holds banded values (same semantic as Age Group);
  "APR DRG Description and Code" holds bare codes; plain
  "APR Severity of Illness" holds codes that year; no medical/surgical column
  exists (staged NULL, 100% for 2011).
- Money arrives plain ("3743.25") from the resource endpoint and
  dollar-formatted ("$1,234.56") in the bulk export; both parse to DOUBLE.

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
