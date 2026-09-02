"""Raw staging into DuckDB plus canonical field mapping across annual schemas.

Design notes:

- Header styles: the bulk CSV export uses display headers ("Length of Stay")
  while the Socrata resource endpoint uses API headers ("length_of_stay").
  Both resolve to one canonical field by comparing normalized forms
  (lowercase, non-alphanumerics stripped).
- Required fields: a file whose headers cannot resolve the required canonical
  set is refused, with every missing field named in the error.
- Typing: SPARCS caps length of stay at "120 +", staged as 120 with
  los_capped flagged. Money fields are stripped of "$" and thousands
  separators before casting.
- Clinical grouping break: ccsr_* and ccs_* columns pass through as-is and
  are never mapped onto each other (documented cross-year limitation).
- apr_severity_of_illness resolves only from the *_code column; the plain
  description column stays unmapped by design and is reported as dropped.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path

import duckdb

from src.config import DUCKDB_PATH, RAW_DIR, ensure_data_dirs, get_logger

logger = get_logger(__name__)

# canonical field -> acceptable source header aliases (normalized on compare).
# Documented source renames covered here:
# - "Source of Payment 1/2/3" (through 2016) -> "Payment Typology 1/2/3" (2017+)
# - "Health Service Area" vs "Hospital Service Area" naming alternates by year
# - "APR Medical Surgical Description" (word form, through 2016) vs code form
# - "Sex" (2011) vs "Gender"
# 2011 deviations verified against a 50,000-row sample on 2026-09-02:
# "Age" holds the same banded values as "Age Group"; the field named
# "APR DRG Description and Code" holds bare codes; the plain
# "APR Severity of Illness" column holds numeric codes that year (in later
# years the plain column is the word description, so alias priority prefers
# the *_code column whenever both exist). 2011 carries no medical/surgical
# column at all; it is staged as NULL for that year.
CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "health_service_area": ("health_service_area", "hospital_service_area"),
    "hospital_county": ("hospital_county",),
    "operating_certificate_number": (
        "operating_certificate_number",
        "operating_certificate",
    ),
    "facility_id": ("permanent_facility_id", "facility_id", "pfi"),
    "facility_name": ("facility_name",),
    "age_group": ("age_group", "age"),
    "zip_code": ("zip_code", "zip_code_3", "zip_code_3_digits", "zip"),
    "gender": ("gender", "sex"),
    "race": ("race",),
    "ethnicity": ("ethnicity",),
    "length_of_stay": ("length_of_stay", "los"),
    "type_of_admission": ("type_of_admission", "admission_type"),
    "patient_disposition": ("patient_disposition", "disposition"),
    "discharge_year": ("discharge_year",),
    "apr_drg_code": ("apr_drg_code", "apr_drg_description_and_code"),
    "apr_drg_description": ("apr_drg_description",),
    "apr_mdc_code": ("apr_mdc_code",),
    "apr_mdc_description": ("apr_mdc_description",),
    # earlier alias wins when several source columns map to the same canonical
    "apr_severity_of_illness": (
        "apr_severity_of_illness_code",
        "apr_severity_of_illness",
    ),
    "apr_risk_of_mortality": (
        "apr_risk_of_mortality_code",
        "apr_risk_of_mortality",
    ),
    "apr_medical_surgical": (
        "apr_medical_surgical",
        "apr_medical_surgical_description",
    ),
    "payment_typology_1": ("payment_typology_1", "source_of_payment_1"),
    "payment_typology_2": ("payment_typology_2", "source_of_payment_2"),
    "payment_typology_3": ("payment_typology_3", "source_of_payment_3"),
    "birth_weight": ("birth_weight",),
    "emergency_department_indicator": ("emergency_department_indicator",),
    "total_charges": ("total_charges",),
    "total_costs": ("total_costs",),
    "ccsr_diagnosis_code": ("ccsr_diagnosis_code",),
    "ccsr_diagnosis_description": ("ccsr_diagnosis_description",),
    "ccsr_procedure_code": ("ccsr_procedure_code",),
    "ccsr_procedure_description": ("ccsr_procedure_description",),
    "ccs_diagnosis_code": ("ccs_diagnosis_code",),
    "ccs_diagnosis_description": ("ccs_diagnosis_description",),
    "ccs_procedure_code": ("ccs_procedure_code",),
    "ccs_procedure_description": ("ccs_procedure_description",),
}

# Columns that must exist (they drive every mart); values may still be blank.
REQUIRED = frozenset(
    {
        "discharge_year",
        "facility_id",
        "facility_name",
        "length_of_stay",
        "type_of_admission",
        "patient_disposition",
        "apr_drg_code",
        "apr_severity_of_illness",
        "payment_typology_1",
        "emergency_department_indicator",
        "total_charges",
        "total_costs",
    }
)

BIGINT_FIELDS = frozenset({"discharge_year", "length_of_stay", "birth_weight"})
MONEY_FIELDS = frozenset({"total_charges", "total_costs"})

# DDL column order is the canonical order everywhere in staging.
CANONICAL_FIELDS: tuple[str, ...] = tuple(CANONICAL_ALIASES)

STAGING_DDL = """
CREATE TABLE stg_discharges (
    source_year BIGINT,
    source_file VARCHAR,
    los_capped BOOLEAN,
    health_service_area VARCHAR,
    hospital_county VARCHAR,
    operating_certificate_number VARCHAR,
    facility_id VARCHAR,
    facility_name VARCHAR,
    age_group VARCHAR,
    zip_code VARCHAR,
    gender VARCHAR,
    race VARCHAR,
    ethnicity VARCHAR,
    length_of_stay BIGINT,
    type_of_admission VARCHAR,
    patient_disposition VARCHAR,
    discharge_year BIGINT,
    apr_drg_code VARCHAR,
    apr_drg_description VARCHAR,
    apr_mdc_code VARCHAR,
    apr_mdc_description VARCHAR,
    apr_severity_of_illness VARCHAR,
    apr_risk_of_mortality VARCHAR,
    apr_medical_surgical VARCHAR,
    payment_typology_1 VARCHAR,
    payment_typology_2 VARCHAR,
    payment_typology_3 VARCHAR,
    birth_weight BIGINT,
    emergency_department_indicator VARCHAR,
    total_charges DOUBLE,
    total_costs DOUBLE,
    ccsr_diagnosis_code VARCHAR,
    ccsr_diagnosis_description VARCHAR,
    ccsr_procedure_code VARCHAR,
    ccsr_procedure_description VARCHAR,
    ccs_diagnosis_code VARCHAR,
    ccs_diagnosis_description VARCHAR,
    ccs_procedure_code VARCHAR,
    ccs_procedure_description VARCHAR
)
"""

LOS_CAP_PATTERN = "^120 *\\+$"


class IngestionError(RuntimeError):
    """Raised when a source file cannot be staged canonically."""


def normalize_header(header: str) -> str:
    """Lowercase and strip non-alphanumerics: 'Length of Stay' -> 'lengthofstay'."""
    return re.sub(r"[^a-z0-9]", "", header.lower().strip())


_ALIAS_PRIORITY = {
    normalize_header(alias): (canonical, rank)
    for canonical, aliases in CANONICAL_ALIASES.items()
    for rank, alias in enumerate(aliases)
}


def resolve_columns(
    headers: Sequence[str], required: Iterable[str] = REQUIRED
) -> tuple[dict[str, str], list[str], frozenset[str]]:
    """Map source headers to canonical fields.

    Returns (source_header -> canonical mapping, unmapped source headers,
    missing required canonical fields). When several source columns map to
    the same canonical field, the earlier alias in CANONICAL_ALIASES wins;
    use preferred_sources for the winning column.
    """
    mapping, unmapped, _, best = _resolve_with_best(headers)
    missing = frozenset(required) - set(best)
    return mapping, unmapped, missing


def preferred_sources(headers: Sequence[str]) -> dict[str, str]:
    """Winning source column per canonical field, honoring alias priority."""
    _, _, _, best = _resolve_with_best(headers)
    return {canonical: header for canonical, (_, header) in best.items()}


def _resolve_with_best(
    headers: Sequence[str],
) -> tuple[dict[str, str], list[str], frozenset[str], dict[str, tuple[int, str]]]:
    mapping: dict[str, str] = {}
    unmapped: list[str] = []
    best: dict[str, tuple[int, str]] = {}
    for header in headers:
        hit = _ALIAS_PRIORITY.get(normalize_header(header))
        if hit is None:
            unmapped.append(header)
            continue
        canonical, rank = hit
        mapping[header] = canonical
        if canonical not in best or rank < best[canonical][0]:
            best[canonical] = (rank, header)
    return mapping, unmapped, frozenset(), best


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def los_expression(source_column: str) -> str:
    column = _quote_identifier(source_column)
    return (
        f"CASE WHEN regexp_matches(trim({column}), '{LOS_CAP_PATTERN}') "
        f"THEN 120 ELSE TRY_CAST(trim({column}) AS BIGINT) END"
    )


def money_expression(source_column: str) -> str:
    column = _quote_identifier(source_column)
    return f"TRY_CAST(regexp_replace(trim({column}), '[$,]', '', 'g') AS DOUBLE)"


def canonical_expression(canonical: str, source_column: str | None) -> str:
    """Build the SELECT expression for one canonical field."""
    if source_column is None:
        sql_type = (
            "DOUBLE"
            if canonical in MONEY_FIELDS
            else ("BIGINT" if canonical in BIGINT_FIELDS else "VARCHAR")
        )
        return f"CAST(NULL AS {sql_type})"
    if canonical == "length_of_stay":
        return los_expression(source_column)
    if canonical in MONEY_FIELDS:
        return money_expression(source_column)
    if canonical in BIGINT_FIELDS:
        return f"TRY_CAST(trim({_quote_identifier(source_column)}) AS BIGINT)"
    return _quote_identifier(source_column)


def csv_columns(conn: duckdb.DuckDBPyConnection, csv_path: Path) -> list[str]:
    """Read the header row of a CSV via DuckDB without loading the file."""
    relation = conn.sql(
        f"SELECT * FROM read_csv({_sql_literal(csv_path.as_posix())}, "
        "header=true, all_varchar=true) LIMIT 0"
    )
    return list(relation.columns)


def ensure_staging(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(STAGING_DDL)


def reset_staging(conn: duckdb.DuckDBPyConnection) -> None:
    """Drop and recreate the staging table for a full-refresh run."""
    conn.execute("DROP TABLE IF EXISTS stg_discharges")
    ensure_staging(conn)


def ingest_file(
    conn: duckdb.DuckDBPyConnection,
    csv_path: Path,
    year: int,
    required: Iterable[str] = REQUIRED,
) -> int:
    """Stage one annual CSV into stg_discharges; returns rows inserted."""
    headers = csv_columns(conn, csv_path)
    if len(headers) < 10:
        raise IngestionError(
            f"{csv_path.name}: header row has {len(headers)} columns; "
            "expected a comma-delimited SPARCS export"
        )
    mapping, unmapped, missing = resolve_columns(headers, required)
    if missing:
        raise IngestionError(
            f"{csv_path.name}: missing required canonical fields: " + ", ".join(sorted(missing))
        )
    if unmapped:
        logger.warning(
            "%s: dropping unmapped source columns: %s",
            csv_path.name,
            ", ".join(unmapped),
        )
    reverse = preferred_sources(headers)
    los_capped_expr = (
        f"regexp_matches(trim({_quote_identifier(reverse['length_of_stay'])}), '{LOS_CAP_PATTERN}')"
    )
    select_parts = [
        f"CAST({year} AS BIGINT) AS source_year",
        f"{_sql_literal(csv_path.name)} AS source_file",
        los_capped_expr + " AS los_capped",
    ]
    select_parts += [
        f"{canonical_expression(field, reverse.get(field))} AS {field}"
        for field in CANONICAL_FIELDS
    ]
    conn.execute(
        f"INSERT INTO stg_discharges SELECT {', '.join(select_parts)} "
        f"FROM read_csv({_sql_literal(csv_path.as_posix())}, "
        "header=true, all_varchar=true)"
    )
    count = conn.execute(
        "SELECT COUNT(*) FROM stg_discharges WHERE source_year = ?", [year]
    ).fetchone()[0]
    logger.info("%s: staged %s rows for %s", csv_path.name, count, year)
    return int(count)


def discover_raw_files(raw_dir: Path | None = None) -> dict[int, Path]:
    """Find downloaded annual files, keyed by year parsed from the filename."""
    directory = raw_dir if raw_dir is not None else RAW_DIR
    found: dict[int, Path] = {}
    for path in sorted(directory.glob("sparcs_inpatient_*.csv")):
        match = re.search(r"(\d{4})", path.stem)
        if match:
            found[int(match.group(1))] = path
    return found


def main() -> int:
    """Ingest every downloaded annual file into a fresh staging table."""
    ensure_data_dirs()
    files = discover_raw_files()
    if not files:
        logger.error("No SPARCS CSV files found in %s", RAW_DIR)
        return 1
    conn = duckdb.connect(str(DUCKDB_PATH))
    try:
        reset_staging(conn)
        for year, path in sorted(files.items()):
            ingest_file(conn, path, year)
        summary = conn.execute(
            "SELECT source_year, COUNT(*) AS rows, SUM(los_capped) AS los_capped "
            "FROM stg_discharges GROUP BY source_year ORDER BY source_year"
        ).fetchall()
        for source_year, rows, capped in summary:
            logger.info(
                "staging summary: %s -> %s rows (los_capped: %s)",
                source_year,
                rows,
                capped,
            )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
