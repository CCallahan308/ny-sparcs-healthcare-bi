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

Milestone-gated delivery. Milestone 0 (foundation) complete: structure,
tooling, CI. See [docs/architecture.md](docs/architecture.md) for milestone
status.

## License

[MIT](LICENSE)
