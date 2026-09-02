"""Smoke tests: package import, deterministic paths, data directory creation."""

from src import config


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
