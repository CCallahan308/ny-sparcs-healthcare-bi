"""App smoke tests: package import, paths, and every page rendering headlessly.

Pages run against fixture-built marts through a monkeypatched marts
directory, so CI needs no real SPARCS downloads.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from src import config
from src.transform import run_transformations
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).parents[1] / "app"
PAGES = [
    "Home.py",
    "pages/1_Executive_Summary.py",
    "pages/2_Service_Lines.py",
    "pages/3_Payer_Exposure.py",
    "pages/4_Facility_Benchmarks.py",
    "pages/5_Process_Control.py",
    "pages/6_Data_Quality.py",
]


# --- Foundation smoke tests --------------------------------------------------


def test_config_constants() -> None:
    assert config.HISTORY_START_YEAR == 2009
    assert config.DEFAULT_START_YEAR == 2019
    assert config.DEFAULT_END_YEAR == 2024


def test_2020_is_documented_assignable_cause_period() -> None:
    assert 2020 in config.EXCLUDED_BASELINE_YEARS


def test_paths_derive_from_project_root() -> None:
    assert config.RAW_DIR == config.PROJECT_ROOT / "data" / "raw"
    assert config.DUCKDB_PATH.parent == config.PROCESSED_DIR
    assert (config.PROJECT_ROOT / "pyproject.toml").is_file()
    # No hardcoded local absolute paths: every data path sits under the repo.
    assert str(config.DATA_DIR).startswith(str(config.PROJECT_ROOT))


def test_ensure_data_dirs_creates_tree(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(config, "MARTS_DIR", tmp_path / "marts")
    config.ensure_data_dirs()
    assert (tmp_path / "raw").is_dir()
    assert (tmp_path / "processed").is_dir()
    assert (tmp_path / "marts").is_dir()


# --- App smoke tests ---------------------------------------------------------


@pytest.fixture()
def app_marts(pipeline_conn, tmp_path, monkeypatch):
    run_transformations(pipeline_conn, tmp_path)
    monkeypatch.setattr(config, "MARTS_DIR", tmp_path)
    yield tmp_path


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exceptions(app_marts, page: str) -> None:
    app = AppTest.from_file(str(APP_DIR / page), default_timeout=120)
    app.run()
    assert not app.exception, f"{page} raised: {[e.value for e in app.exception]}"


def test_executive_kpis_reconcile_to_trends(app_marts) -> None:
    from app.components import data

    kpis = data.compute_kpis(data.load_mart("executive_kpis.parquet"))
    trends = data.load_mart("executive_trends.parquet")
    total_discharges = int(trends["discharges"].sum())
    total_cost = float(trends["estimated_cost"].sum())
    assert kpis["discharges"] == total_discharges
    assert kpis["estimated_cost"] == pytest.approx(total_cost)
    assert kpis["cost_per_discharge"] == pytest.approx(total_cost / total_discharges)


def test_contradictory_filters_produce_graceful_empty_state(app_marts) -> None:
    from app.components import data

    frame = data.load_mart("executive_kpis.parquet")
    # The redacted-facility fixture row carries a blank name; skip it.
    facility = sorted(name for name in frame["facility_name"].dropna().unique() if name)[0]
    facility_county = frame.loc[frame["facility_name"] == facility, "county"].iloc[0]
    other_county = next(
        county
        for county in sorted(county for county in frame["county"].dropna().unique() if county)
        if county != facility_county
    )

    app = AppTest.from_file(str(APP_DIR / "pages" / "1_Executive_Summary.py"), default_timeout=120)
    app.run()
    assert not app.exception
    facility_box = next(box for box in app.multiselect if "Facility" in box.label)
    county_box = next(box for box in app.multiselect if "County" in box.label)
    facility_box.set_value([facility]).run()
    county_box = next(box for box in app.multiselect if "County" in box.label)
    county_box.set_value([other_county]).run()
    assert not app.exception
    assert app.info, "expected a graceful empty-state message"
    assert "No discharges match" in app.info[0].value
