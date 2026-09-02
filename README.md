# NY SPARCS Healthcare Operations BI

An in-house healthcare operations BI system built on New York State's public
SPARCS inpatient discharge data: Python, DuckDB, SQL transformations, Parquet
marts, and a Streamlit front end. Version-controlled analytics instead of a
per-seat BI tool dependency.

> "I build version-controlled, in-house healthcare BI systems in Python rather
> than buying a per-seat Tableau dependency."

## Business problem

New York hospital systems operate on thin margins driven by payer mix, case
complexity, and length of stay. A regional system's finance and operations
committee needs one view of where cost and throughput concentrate by facility,
service line, and payer, and which facilities show potential operational
outlier signals after accounting for case complexity.

**Business question.** Where are cost and throughput concentrated by facility,
service line, and payer, and which facilities have potential operational
outlier signals after accounting for case complexity?

## Target users

A regional hospital system's finance and operations committee: executives who
need volume, cost, throughput, severity, payer exposure, and facility-level
performance relative to comparable statewide benchmarks.

## Data source

[Hospital Inpatient Discharges (SPARCS De-Identified)](https://health.data.ny.gov/stories/s/SPARCS-PUF-Story-Page/wvua-rr23/)
public use files published by the New York State Department of Health, annual
releases 2009 through 2024. De-identified public data only. Estimated costs are
DOH-derived estimates; charges are not reimbursement. Payer analysis here is
exposure analysis, not margin analysis. See
[docs/limitations.md](docs/limitations.md) before interpreting any figure.

## Architecture

Bronze (raw annual CSVs) to DuckDB staging (canonical field mapping) to SQL
marts (Parquet) to Streamlit pages that read marts only. Full design in
[docs/architecture.md](docs/architecture.md); metric definitions in
[docs/metric_definitions.md](docs/metric_definitions.md).

## Repository layout

| Path | Responsibility |
|---|---|
| `src/` | Download, ingest, transform, metrics, quality, control charts |
| `sql/` | Staging and mart SQL transformations |
| `data/` | `raw/` (gitignored), `processed/` (gitignored), `marts/` (curated) |
| `app/` | Streamlit app: pages and shared components |
| `scripts/` | One-command pipeline runner and mart validation |
| `tests/` | pytest suite; synthetic fixtures only, never SPARCS extracts |
| `docs/` | Architecture, data dictionary, metric definitions, limitations |

## Local setup

Requires Python 3.11 or 3.12.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
```

Optional: keep large raw files outside the repository (for example when it
lives in a cloud-synced folder) by setting `SPARCS_BI_DATA_ROOT` to another
directory. Marts always stay inside the repository.

Acquire data (sample mode for development, full mode for production marts):

```bash
python -m src.download --sample 50000 --years 2011 2024   # quick samples
python -m src.download --years 2009 2010 2011 2012 2013 2014 2015 2016 \
                            2017 2018 2019 2020 2021 2022 2023 2024   # full, ~10 GB
python -m src.ingest                                      # stage into DuckDB
```

Build marts (one command, implemented in Milestone 2):

```bash
python scripts/run_pipeline.py
```

Run the app (pages arrive in Milestone 4):

```bash
streamlit run app/Home.py
```

## Quality gates

```bash
ruff check .
ruff format --check .
pytest -q
```

CI runs the same gates on every push and pull request.

## Status

Milestone-gated delivery. Milestones 0-2 complete: foundation, source
registry and ingestion across all 16 annual schemas (2009-2024), normalized
staging, the seven Parquet marts, metric module, data-quality output, and a
one-command pipeline. See [docs/architecture.md](docs/architecture.md) for
milestone status and mart grains,
[docs/schema_drift.md](docs/schema_drift.md) for the cross-year schema
report, and [docs/metric_definitions.md](docs/metric_definitions.md) for KPI
definitions.

## License

[MIT](LICENSE)
