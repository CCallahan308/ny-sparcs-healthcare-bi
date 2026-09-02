# Demo marts

Parquet marts in this directory are built from 50,000-row public samples of
three SPARCS annual files (2009, 2011, 2024), not from the full extracts.
They exist so a fresh clone and a hosted deployment render the entire app
without a ~10 GB download.

What that means when reading them:

- Volume, cost, and payer figures are sample quantities, not statewide totals.
- Series that need many years (control-chart baselines, top movers) report
  insufficient data or hide, by design, until full marts are built.
- Facility benchmark values carry wide sample noise; treat them as a display
  of the method, not as findings.

Locally built marts in `data/marts/` (gitignored) always take precedence over
these. Regenerate after rebuilding sample marts:

```bash
python -m src.download --sample 50000 --years 2009 2011 2024
python scripts/run_pipeline.py
python scripts/export_demo_marts.py
```
