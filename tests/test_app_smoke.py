"""App smoke tests: package import, paths, and every page rendering headlessly.

Pages run against fixture-built marts through a monkeypatched marts
directory, so CI needs no real SPARCS downloads.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from src import config
from src.quality import write_run_metadata
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


def test_load_mart_falls_back_to_demo_marts(tmp_path, monkeypatch) -> None:
    """With no locally built marts, committed demo marts serve the app."""
    import pandas as pd
    from app.components import data

    demo = tmp_path / "demo"
    demo.mkdir()
    pd.DataFrame({"year": [2024], "discharges": [7]}).to_parquet(
        demo / "executive_trends.parquet", index=False
    )
    (demo / "run_metadata.json").write_text('{"generated_utc": "test"}', encoding="utf-8")
    monkeypatch.setattr(config, "MARTS_DIR", tmp_path / "empty_marts")
    monkeypatch.setattr(config, "DEMO_MARTS_DIR", demo)

    frame = data.load_mart("executive_trends.parquet")
    assert frame["discharges"].tolist() == [7]
    assert data.load_run_metadata() == {"generated_utc": "test"}
    assert data.is_demo_mart("executive_trends.parquet")
    assert not data.is_demo_mart("missing.parquet")


def test_local_mart_and_metadata_take_precedence_without_hiding_demo_provenance(
    tmp_path, monkeypatch
) -> None:
    import pandas as pd
    from app.components import data

    local, demo = tmp_path / "local", tmp_path / "demo"
    local.mkdir()
    demo.mkdir()
    for directory, discharges in [(local, 19), (demo, 7)]:
        pd.DataFrame({"discharges": [discharges]}).to_parquet(
            directory / "executive_kpis.parquet", index=False
        )
        (directory / "run_metadata.json").write_text(
            json.dumps({"staged_years": [{"year": 2024, "rows": discharges}]}),
            encoding="utf-8",
        )
    monkeypatch.setattr(config, "MARTS_DIR", local)
    monkeypatch.setattr(config, "DEMO_MARTS_DIR", demo)

    assert data.load_mart("executive_kpis.parquet")["discharges"].tolist() == [19]
    assert not data.is_demo_mart("executive_kpis.parquet")
    assert data.load_run_metadata()["staged_years"][0]["rows"] == 19
    assert data.load_demo_run_metadata()["staged_years"][0]["rows"] == 7


@pytest.fixture()
def app_marts(pipeline_conn, tmp_path, monkeypatch):
    row_counts = run_transformations(pipeline_conn, tmp_path)
    write_run_metadata(pipeline_conn, tmp_path, row_counts, {})
    monkeypatch.setattr(config, "MARTS_DIR", tmp_path)
    yield tmp_path


@pytest.fixture()
def demo_app_marts(app_marts, tmp_path, monkeypatch):
    """Serve only synthetic fixture-built marts through the sample fallback."""
    monkeypatch.setattr(config, "DEMO_MARTS_DIR", app_marts)
    monkeypatch.setattr(config, "MARTS_DIR", tmp_path / "no_local_marts")
    yield app_marts


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exceptions(app_marts, page: str) -> None:
    app = AppTest.from_file(str(APP_DIR / page), default_timeout=120)
    app.run()
    assert not app.exception, f"{page} raised: {[e.value for e in app.exception]}"
    assert not any("Sample data demo" in notice.value for notice in app.info)
    if page == "pages/5_Process_Control.py":
        assert app.selectbox[0].options[0].startswith("Selected data")


@pytest.mark.parametrize("page", PAGES)
def test_sample_pages_disclose_actual_fixture_provenance(demo_app_marts, page: str) -> None:
    metadata = json.loads((demo_app_marts / "run_metadata.json").read_text(encoding="utf-8"))
    app = AppTest.from_file(str(APP_DIR / page), default_timeout=120)
    app.run()

    assert not app.exception, f"{page} raised: {[e.value for e in app.exception]}"
    notices = [notice.value for notice in app.info if "Sample data demo" in notice.value]
    assert len(notices) == 1
    provenance = next(
        element.value for element in app.markdown if "Public record samples:" in element.value
    )
    for entry in metadata["staged_years"]:
        assert f"{entry['year']} ({entry['rows']:,} records)" in provenance
    assert "not statewide totals or hospital performance findings" in notices[0]
    assert any(expander.label == "Sample years and provenance" for expander in app.expander)
    if page == "pages/5_Process_Control.py":
        assert app.selectbox[0].options[0].startswith("Sample")
        assert app.warning, "three fixture years cannot establish control limits"
    if page == "pages/4_Facility_Benchmarks.py":
        assert any("patterns in the sample" in element.value for element in app.markdown)


def test_mixed_build_discloses_only_the_page_using_sample_marts(
    demo_app_marts, tmp_path, monkeypatch
) -> None:
    local = tmp_path / "partial_local_build"
    local.mkdir()
    shutil.copy2(demo_app_marts / "executive_kpis.parquet", local / "executive_kpis.parquet")
    monkeypatch.setattr(config, "MARTS_DIR", local)

    executive = AppTest.from_file(
        str(APP_DIR / "pages/1_Executive_Summary.py"), default_timeout=120
    )
    executive.run()
    assert not executive.exception
    assert not any("Sample data demo" in notice.value for notice in executive.info)

    process = AppTest.from_file(str(APP_DIR / "pages/5_Process_Control.py"), default_timeout=120)
    process.run()
    assert not process.exception
    assert any("Sample data demo" in notice.value for notice in process.info)
    assert process.selectbox[0].options[0].startswith("Sample")


def test_missing_demo_metadata_keeps_sample_disclosure(demo_app_marts) -> None:
    (demo_app_marts / "run_metadata.json").unlink()
    app = AppTest.from_file(str(APP_DIR / "pages/1_Executive_Summary.py"), default_timeout=120)
    app.run()
    assert not app.exception
    assert any("Sample data demo" in notice.value for notice in app.info)


@pytest.mark.parametrize("mart_source", ["local", "demo"])
@pytest.mark.parametrize("metadata_present", [True, False])
def test_data_quality_metadata_stays_with_its_mart_source(
    demo_app_marts, tmp_path, monkeypatch, mart_source: str, metadata_present: bool
) -> None:
    from app.components import data

    expected = json.loads((demo_app_marts / "run_metadata.json").read_text(encoding="utf-8"))
    local = tmp_path / "local_metadata_build"
    local.mkdir()
    if mart_source == "local":
        shutil.copy2(
            demo_app_marts / "data_quality_summary.parquet", local / "data_quality_summary.parquet"
        )
    source_dir = local if mart_source == "local" else demo_app_marts
    unrelated_dir = demo_app_marts if mart_source == "local" else local
    (source_dir / "run_metadata.json").write_text(json.dumps(expected), encoding="utf-8")
    unrelated = {
        **expected,
        "staged_years": [{"year": 2099, "rows": 999999, "distinct_facilities": 1}],
    }
    (unrelated_dir / "run_metadata.json").write_text(json.dumps(unrelated), encoding="utf-8")
    if not metadata_present:
        (source_dir / "run_metadata.json").unlink()
    monkeypatch.setattr(config, "MARTS_DIR", local)

    metadata = data.load_run_metadata("data_quality_summary.parquet")
    assert metadata == (expected if metadata_present else None)
    app = AppTest.from_file(str(APP_DIR / "pages/6_Data_Quality.py"), default_timeout=120)
    app.run()
    assert not app.exception
    row_metrics = [metric.value for metric in app.metric if metric.label == "Rows staged"]
    if metadata_present:
        assert row_metrics == [f"{sum(entry['rows'] for entry in expected['staged_years']):,}"]
    else:
        assert not row_metrics
        assert any("beside the displayed data-quality mart" in notice.value for notice in app.info)


def test_executive_kpis_reconcile_to_trends(app_marts) -> None:
    from app.components import data

    kpis = data.compute_kpis(data.load_mart("executive_kpis.parquet"))
    trends = data.load_mart("executive_trends.parquet")
    total_discharges = int(trends["discharges"].sum())
    total_cost = float(trends["estimated_cost"].sum())
    assert kpis["discharges"] == total_discharges
    assert kpis["estimated_cost"] == pytest.approx(total_cost)
    assert kpis["cost_per_discharge"] == pytest.approx(total_cost / total_discharges)


def test_sample_executive_defaults_include_every_year_and_prior_comparison(demo_app_marts) -> None:
    app = AppTest.from_file(str(APP_DIR / "pages/1_Executive_Summary.py"), default_timeout=120)
    app.run()

    assert not app.exception
    assert app.slider[0].value == (2009, 2024)
    assert any("Focus year: 2024 (deltas vs 2011)" in element.value for element in app.markdown)


@pytest.mark.parametrize(
    ("years", "include_all_years", "expected_start"),
    [
        ([2009, 2011, 2024], False, 2009),
        ([2009, 2019, 2024], False, 2019),
        ([2009, 2019, 2024], True, 2009),
    ],
)
def test_year_range_uses_available_years_and_retains_local_recent_default(
    years: list[int], include_all_years: bool, expected_start: int
) -> None:
    app = AppTest.from_string(
        "import pandas as pd\n"
        "from app.components import filters\n"
        f"filters.year_range(pd.DataFrame({{'discharge_year': {years!r}}}), "
        f"include_all_years={include_all_years!r})"
    ).run()

    assert not app.exception
    assert app.slider[0].value == (expected_start, max(years))


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
