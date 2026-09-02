"""Download annual SPARCS inpatient CSVs from the Socrata source registry.

Two modes:

- Sample (default in development): --sample N pulls the first N rows through
  the Socrata resource endpoint. API-style headers. Small and fast; used for
  ingestion development and CI-safe local runs. Sample files are recorded in
  the raw manifest and never misrepresented as complete annual extracts.
- Full: bulk export of the complete annual file via rows.csv. Large (hundreds
  of MB per year); used for production mart builds.

Both modes stream to a .part file and rename atomically on success, retry on
connection errors and throttle statuses, and log clearly.
"""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter, Retry

from src.config import RAW_DIR, SOURCE_REGISTRY, ensure_data_dirs, get_logger

logger = get_logger(__name__)

MANIFEST_PATH = RAW_DIR / "_manifest.json"
CHUNK_SIZE = 1024 * 1024
STATUS_FORCERETRY = (429, 500, 502, 503, 504)


def load_registry(path: Path = SOURCE_REGISTRY) -> dict[int, dict]:
    """Load the committed source registry: year -> {id, domain, ...}."""
    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    return {int(year): meta for year, meta in data["years"].items()}


def build_url(year_meta: dict, sample_rows: int | None = None) -> str:
    if sample_rows is not None:
        return f"https://{year_meta['domain']}/resource/{year_meta['id']}.csv?$limit={sample_rows}"
    return f"https://{year_meta['domain']}/api/views/{year_meta['id']}/rows.csv?accessType=DOWNLOAD"


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=2,
        backoff_factor=1.5,
        status_forcelist=STATUS_FORCERETRY,
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = "ny-sparcs-healthcare-bi/0.1 (data pipeline)"
    return session


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    return {"files": {}}


def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def validate_file(path: Path) -> None:
    """Fail loudly on empty files or non-CSV content."""
    size = path.stat().st_size
    if size == 0:
        raise RuntimeError(f"{path.name}: downloaded file is empty")
    with open(path, encoding="utf-8", errors="replace") as handle:
        header = handle.readline()
    comma_count = header.count(",")
    if comma_count < 10:
        raise RuntimeError(
            f"{path.name}: header row contains {comma_count} commas; "
            "expected a comma-delimited SPARCS export"
        )


def download_year(
    session: requests.Session,
    registry: dict[int, dict],
    year: int,
    sample_rows: int | None = None,
    force: bool = False,
) -> Path:
    """Download one year's file; skips existing files unless force=True."""
    if year not in registry:
        raise KeyError(f"{year} is not in the source registry")
    destination = RAW_DIR / f"sparcs_inpatient_{year}.csv"
    if destination.exists() and not force:
        logger.info("%s already exists; skipping (use force to redownload)", destination.name)
        return destination

    url = build_url(registry[year], sample_rows)
    logger.info("downloading %s", url)
    response = session.get(url, stream=True, timeout=(10, 300))
    response.raise_for_status()

    part_path = destination.with_suffix(".csv.part")
    bytes_written = 0
    with open(part_path, "wb") as handle:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            handle.write(chunk)
            bytes_written += len(chunk)
    part_path.replace(destination)
    validate_file(destination)

    manifest = _load_manifest()
    manifest["files"][destination.name] = {
        "url": url,
        "bytes": bytes_written,
        "sample_rows": sample_rows,
        "registry_id": registry[year]["id"],
    }
    _save_manifest(manifest)
    logger.info("%s: %s bytes written and validated", destination.name, f"{bytes_written:,}")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Download SPARCS annual files")
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="download only the first N rows (development mode)",
    )
    parser.add_argument("--force", action="store_true", help="redownload existing files")
    args = parser.parse_args()

    ensure_data_dirs()
    registry = load_registry()
    session = build_session()
    failures: list[str] = []
    for year in args.years:
        try:
            download_year(session, registry, year, sample_rows=args.sample, force=args.force)
        except Exception as error:  # noqa: BLE001 - log and continue other years
            logger.error("download failed for %s: %s", year, error)
            failures.append(str(year))
    if failures:
        logger.error("failed years: %s", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
