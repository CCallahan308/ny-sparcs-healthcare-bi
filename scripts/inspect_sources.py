"""Discover SPARCS annual datasets, inspect schemas, emit the source registry.

Requires network access. Not run by CI; the committed artifacts record the
access date. Outputs:

- src/sources.toml             static registry used by download.py
- docs/schema_report.json      machine-readable per-year metadata
- docs/schema_drift.md         human schema-drift report against the canonical model
- data/processed/source_metadata.json  same payload as schema_report, working copy

Usage: python scripts/inspect_sources.py [--domain-only health.data.ny.gov]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import PROCESSED_DIR, get_logger  # noqa: E402
from src.ingest import CANONICAL_FIELDS, resolve_columns  # noqa: E402

logger = get_logger("inspect_sources")

DOMAINS = ["health.data.ny.gov", "healthdata.gov"]
DOMAIN_PRIORITY = {"health.data.ny.gov": 0, "healthdata.gov": 1}
QUERY = '"Hospital Inpatient Discharges" "SPARCS De-Identified"'

REGISTRY_PATH = PROJECT_ROOT / "src" / "sources.toml"
REPORT_JSON_PATH = PROJECT_ROOT / "docs" / "schema_report.json"
REPORT_MD_PATH = PROJECT_ROOT / "docs" / "schema_drift.md"


def fetch_catalog(session: requests.Session, domain: str) -> list[dict]:
    response = session.get(
        f"https://{domain}/api/catalog/v1",
        params={"q": QUERY, "limit": 100},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("results", [])


# The annual files are named exactly "Hospital Inpatient Discharges
# (SPARCS De-Identified): YYYY". Derived datasets (PQI, PPR, PSI, Cost
# Transparency, ...) share the prefix but a different suffix and are excluded.
ANNUAL_NAME = re.compile(
    r"Hospital Inpatient Discharges \(SPARCS De-Identified\): ((?:19|20)\d{2})\Z"
)


def candidate_datasets(session: requests.Session, domains: Sequence[str]) -> list[dict]:
    """Return annual SPARCS inpatient de-identified datasets with year and domain."""
    candidates: list[dict] = []
    seen_ids: set[str] = set()
    for domain in domains:  # domains are ordered by preference
        for result in fetch_catalog(session, domain):
            resource = result.get("resource", {})
            name = resource.get("name", "")
            dataset_id = resource.get("id", "")
            if dataset_id in seen_ids:
                continue
            match = ANNUAL_NAME.fullmatch(name.strip())
            if not match:
                continue
            seen_ids.add(dataset_id)
            candidates.append(
                {
                    "domain": domain,
                    "id": dataset_id,
                    "name": name.strip(),
                    "year": int(match.group(1)),
                }
            )
    return candidates


def fetch_view(session: requests.Session, domain: str, dataset_id: str) -> dict:
    response = session.get(f"https://{domain}/api/views/{dataset_id}.json", timeout=30)
    response.raise_for_status()
    return response.json()


def analyze_view(view: dict) -> dict:
    columns = view.get("columns", [])
    api_columns = [column.get("fieldName", "") for column in columns]
    display_columns = [column.get("name", "") for column in columns]
    rows = int(
        max(
            (column.get("cachedContents", {}).get("count") or 0 for column in columns),
            default=0,
        )
    )
    mapping, unmapped_api, _ = resolve_columns(api_columns, required=())
    resolved = set(mapping.values())
    missing_canonical = [field for field in CANONICAL_FIELDS if field not in resolved]
    family = []
    if any(column.startswith("ccsr_") for column in api_columns):
        family.append("CCSR")
    if any(column.startswith("ccs_") for column in api_columns):
        family.append("CCS")
    return {
        "rows": rows,
        "column_count": len(columns),
        "api_columns": api_columns,
        "display_columns": display_columns,
        "unmapped_api_columns": unmapped_api,
        "missing_canonical": missing_canonical,
        "clinical_grouping_family": " + ".join(family) or "none",
    }


def choose_preferred(datasets: list[dict]) -> dict[int, dict]:
    """Prefer health.data.ny.gov, then the copy with more rows."""
    preferred: dict[int, dict] = {}
    for dataset in datasets:
        current = preferred.get(dataset["year"])
        rank = (
            DOMAIN_PRIORITY.get(dataset["domain"], 9),
            -dataset["rows"],
        )
        if current is None or rank < current["_rank"]:
            dataset = {**dataset, "_rank": rank}
            preferred[dataset["year"]] = dataset
    return {year: meta for year, meta in sorted(preferred.items())}


def write_registry(preferred: dict[int, dict], access_date: str) -> None:
    lines = [
        "# Static registry of SPARCS de-identified inpatient annual datasets.",
        f"# Generated by scripts/inspect_sources.py on {access_date} from live",
        "# Socrata catalogs. Row counts are the observed counts on that date.",
        "",
    ]
    for year, meta in preferred.items():
        lines.append(f"[years.{year}]")
        lines.append(f'id = "{meta["id"]}"')
        lines.append(f'domain = "{meta["domain"]}"')
        lines.append(f"rows = {meta['rows']}")
        lines.append(f'access_date = "{access_date}"')
        lines.append(f'clinical_grouping = "{meta["clinical_grouping_family"]}"')
        lines.append("")
    REGISTRY_PATH.write_text("\n".join(lines), encoding="utf-8")
    logger.info("registry written: %s", REGISTRY_PATH)


def write_reports(preferred: dict[int, dict], generated_utc: str) -> None:
    payload = {
        "generated_utc": generated_utc,
        "years": {
            str(year): {
                "dataset_id": meta["id"],
                "domain": meta["domain"],
                "dataset_name": meta["name"],
                "rows": meta["rows"],
                "column_count": meta["column_count"],
                "clinical_grouping_family": meta["clinical_grouping_family"],
                "unmapped_api_columns": meta["unmapped_api_columns"],
                "missing_canonical": meta["missing_canonical"],
                "api_columns": meta["api_columns"],
                "display_columns": meta["display_columns"],
            }
            for year, meta in preferred.items()
        },
    }
    REPORT_JSON_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (PROCESSED_DIR / "source_metadata.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    md = [
        "# Schema drift report",
        "",
        f"Generated {generated_utc} by `scripts/inspect_sources.py` from live Socrata",
        "catalog metadata. Comparison target: the canonical staging model in",
        "`src/ingest.py` (`CANONICAL_ALIASES`).",
        "",
        "## Summary by year",
        "",
        "| Year | Dataset ID | Domain | Rows | Columns | Grouping | Missing canonical |",
        "|---|---|---|---|---|---|---|",
    ]
    for year, meta in sorted(preferred.items()):
        missing = ", ".join(meta["missing_canonical"]) or "none"
        md.append(
            f"| {year} | {meta['id']} | {meta['domain']} | {meta['rows']:,} "
            f"| {meta['column_count']} | {meta['clinical_grouping_family']} "
            f"| {missing} |"
        )
    md += [
        "",
        "## Notes",
        "",
        "- Missing canonical fields are staged as NULL for that year; the marts",
        "  layer documents which analyses are available per year.",
        "- `apr_severity_of_illness` resolves only from the `*_code` column; the",
        "  description column is intentionally unmapped (1:1 with the code).",
        "- CCS and CCSR families are kept separate; they are never mapped onto",
        "  each other across years.",
        "- Dropped source columns per year are recorded in",
        "  `docs/schema_report.json` (`unmapped_api_columns`).",
        "",
    ]
    REPORT_MD_PATH.write_text("\n".join(md), encoding="utf-8")
    logger.info("report written: %s", REPORT_MD_PATH)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect SPARCS source schemas")
    parser.add_argument(
        "--domains",
        nargs="+",
        default=DOMAINS,
        help="Socrata domains to search",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = "ny-sparcs-healthcare-bi/0.1 (schema inspection)"
    candidates = candidate_datasets(session, args.domains)
    logger.info("candidate datasets found: %s", len(candidates))
    if not candidates:
        logger.error("no SPARCS de-identified inpatient datasets found")
        return 1

    analyzed: list[dict] = []
    for dataset in candidates:
        try:
            view = fetch_view(session, dataset["domain"], dataset["id"])
        except requests.HTTPError as error:
            # Stale catalog entries 404 on their view metadata; the picker
            # falls back to the healthy copy for that year.
            logger.warning("skipping %s (%s): %s", dataset["id"], dataset["year"], error)
            continue
        analyzed.append({**dataset, **analyze_view(view)})
        logger.info(
            "%s %s: %s rows, %s columns",
            dataset["year"],
            dataset["id"],
            f"{analyzed[-1]['rows']:,}",
            analyzed[-1]["column_count"],
        )

    if not analyzed:
        logger.error("no dataset view metadata could be fetched")
        return 1

    preferred = choose_preferred(analyzed)
    access_date = date.today().isoformat()
    generated_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    write_registry(preferred, access_date)
    write_reports(preferred, generated_utc)

    years = sorted(preferred)
    logger.info("registry covers %s years: %s..%s", len(years), years[0], years[-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
