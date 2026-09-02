# Schema drift report

Generated 2026-09-02 17:13 UTC by `scripts/inspect_sources.py` from live Socrata
catalog metadata. Comparison target: the canonical staging model in
`src/ingest.py` (`CANONICAL_ALIASES`).

## Summary by year

| Year | Dataset ID | Domain | Rows | Columns | Grouping | Missing canonical |
|---|---|---|---|---|---|---|
| 2009 | q6hk-esrj | health.data.ny.gov | 2,665,414 | 34 | CCS | ccsr_diagnosis_code, ccsr_diagnosis_description, ccsr_procedure_code, ccsr_procedure_description |
| 2010 | mtfm-rxf4 | health.data.ny.gov | 2,622,133 | 34 | CCS | ccsr_diagnosis_code, ccsr_diagnosis_description, ccsr_procedure_code, ccsr_procedure_description |
| 2011 | pyhr-5eas | health.data.ny.gov | 2,589,121 | 34 | CCS | apr_medical_surgical, ccsr_diagnosis_code, ccsr_diagnosis_description, ccsr_procedure_code, ccsr_procedure_description |
| 2012 | u4ud-w55t | health.data.ny.gov | 2,544,543 | 34 | CCS | ccsr_diagnosis_code, ccsr_diagnosis_description, ccsr_procedure_code, ccsr_procedure_description |
| 2013 | npsr-cm47 | health.data.ny.gov | 2,428,905 | 34 | CCS | ccsr_diagnosis_code, ccsr_diagnosis_description, ccsr_procedure_code, ccsr_procedure_description |
| 2014 | rmwa-zns4 | health.data.ny.gov | 2,367,550 | 34 | CCS | ccsr_diagnosis_code, ccsr_diagnosis_description, ccsr_procedure_code, ccsr_procedure_description |
| 2015 | 82xm-y6g8 | health.data.ny.gov | 2,346,931 | 34 | CCS | ccsr_diagnosis_code, ccsr_diagnosis_description, ccsr_procedure_code, ccsr_procedure_description |
| 2016 | gnzp-ekau | health.data.ny.gov | 2,343,429 | 34 | CCS | ccsr_diagnosis_code, ccsr_diagnosis_description, ccsr_procedure_code, ccsr_procedure_description |
| 2017 | 22g3-z7e7 | health.data.ny.gov | 2,343,569 | 34 | CCS | ccsr_diagnosis_code, ccsr_diagnosis_description, ccsr_procedure_code, ccsr_procedure_description |
| 2018 | yjgt-tq93 | health.data.ny.gov | 2,352,807 | 33 | CCSR | ccs_diagnosis_code, ccs_diagnosis_description, ccs_procedure_code, ccs_procedure_description |
| 2019 | 4ny4-j5zv | health.data.ny.gov | 2,339,462 | 33 | CCSR | ccs_diagnosis_code, ccs_diagnosis_description, ccs_procedure_code, ccs_procedure_description |
| 2020 | nxi5-zj9x | health.data.ny.gov | 2,052,408 | 33 | CCSR | ccs_diagnosis_code, ccs_diagnosis_description, ccs_procedure_code, ccs_procedure_description |
| 2021 | tg3i-cinn | health.data.ny.gov | 2,135,260 | 33 | CCSR | ccs_diagnosis_code, ccs_diagnosis_description, ccs_procedure_code, ccs_procedure_description |
| 2022 | 5dtw-tffi | health.data.ny.gov | 2,103,433 | 33 | CCSR | ccs_diagnosis_code, ccs_diagnosis_description, ccs_procedure_code, ccs_procedure_description |
| 2023 | 46xm-urtu | health.data.ny.gov | 2,125,754 | 33 | CCSR | ccs_diagnosis_code, ccs_diagnosis_description, ccs_procedure_code, ccs_procedure_description |
| 2024 | sf4k-39ay | health.data.ny.gov | 2,196,737 | 33 | CCSR | ccs_diagnosis_code, ccs_diagnosis_description, ccs_procedure_code, ccs_procedure_description |

## Notes

- Missing canonical fields are staged as NULL for that year; the marts
  layer documents which analyses are available per year.
- `apr_severity_of_illness` resolves only from the `*_code` column; the
  description column is intentionally unmapped (1:1 with the code).
- CCS and CCSR families are kept separate; they are never mapped onto
  each other across years.
- Dropped source columns per year are recorded in
  `docs/schema_report.json` (`unmapped_api_columns`).
