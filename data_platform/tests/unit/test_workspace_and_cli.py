import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bank_data.cli import _report_path, app
from bank_data.config import load_config
from bank_data.errors import ConfigurationError, DbtError
from bank_data.ingest.local import LocalSource
from bank_data.reports import meta
from bank_data.settings import DEFAULT_CONFIG_FILE, DEFAULT_SAMPLE_DIR, REPOSITORY_ROOT, PipelineSettings
from bank_data.transform.dbt import DbtResources, DbtRunner, DbtTarget
from bank_data.workspace import Workspace

runner = CliRunner()


def _settings(tmp_path: Path) -> PipelineSettings:
    return PipelineSettings(bank_data_dir=tmp_path, _env_file=None)


def test_each_source_gets_its_own_warehouse(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert Workspace.resolve("s3", pipeline=settings).warehouse_dir == tmp_path / "warehouse"
    assert Workspace.resolve("sample", pipeline=settings).warehouse_dir == tmp_path / "warehouse-sample"
    local = Workspace.resolve("local", local_dir=tmp_path, pipeline=settings)
    assert local.warehouse_dir == tmp_path / "warehouse-local"
    assert Workspace.resolve(None, pipeline=settings).source_kind == "sample"
    override = PipelineSettings(bank_data_warehouse_dir=tmp_path / "custom", _env_file=None)
    assert Workspace.resolve("s3", pipeline=override).warehouse_dir == tmp_path / "custom"


def test_source_options_are_validated(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with pytest.raises(ConfigurationError, match="--local-dir is required"):
        Workspace.resolve("local", pipeline=settings)
    with pytest.raises(ConfigurationError, match="only valid"):
        Workspace.resolve("sample", local_dir=tmp_path, pipeline=settings)


def test_sample_source_reads_the_committed_directory(tmp_path: Path) -> None:
    source = Workspace.resolve("sample", pipeline=_settings(tmp_path)).data_source()
    assert isinstance(source, LocalSource)
    assert source.label == "sample:data_platform/sample"
    assert (DEFAULT_SAMPLE_DIR / "README.md").is_file()


def test_dbt_targets_separate_full_and_subset_builds(tmp_path: Path) -> None:
    space = Workspace.resolve("s3", pipeline=_settings(tmp_path))
    full, subset = space.dbt_target(), space.dbt_target(subset=True)
    assert full.warehouse_db.name == "warehouse.duckdb"
    assert subset.warehouse_db.name == "warehouse-subset.duckdb"
    assert full.gold_dir != subset.gold_dir
    variables = space.dbt_variables(sample_customers=10, sample_seed="s")
    assert variables == {"snapshot_date": "2026-06-17", "lookback_days": 7, "sample_customers": 10, "sample_seed": "s"}


def test_configuration_file_is_parsed_and_validated(tmp_path: Path) -> None:
    config = load_config(DEFAULT_CONFIG_FILE)
    assert config.freshness.for_table("transactions").error_after_hours == 168
    assert config.freshness.for_table("branches").warn_after_hours == 168
    broken = tmp_path / "sources.yml"
    broken.write_text("dataset: {version: x}\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="invalid source configuration"):
        load_config(broken)
    with pytest.raises(ConfigurationError, match="cannot read"):
        load_config(tmp_path / "missing.yml")


def _dbt(tmp_path: Path) -> DbtRunner:
    target = DbtTarget(tmp_path / "w.duckdb", tmp_path / "bronze", tmp_path / "gold", tmp_path / "work")
    return DbtRunner(tmp_path / "project", target, DbtResources(dbt_threads=2, duckdb_threads=3, memory_limit="1GB"))


def test_dbt_environment_carries_paths_but_no_aws_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret-value")
    monkeypatch.setenv("DATA_BUCKET", "fake-bucket")
    environment = _dbt(tmp_path).environment()
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "DATA_BUCKET" not in environment
    assert environment["BANK_DATA_BRONZE_DIR"] == (tmp_path / "bronze").as_posix()
    assert environment["DBT_SEND_ANONYMOUS_USAGE_STATS"] == "false"
    command = _dbt(tmp_path).command(["build", "--full-refresh"], {"lookback_days": 7})
    assert command[1:3] == ["--no-version-check", "--no-use-colors"]
    assert command[-1] == '{"gold_dir": "' + (tmp_path / "gold").as_posix() + '", "lookback_days": 7}'


def test_dbt_failures_raise_with_the_output_tail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner_ = _dbt(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        failed = "test" in command
        return subprocess.CompletedProcess(command, 1 if failed else 0, stdout="line one\nline two\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert "line two" in runner_.build({}, full_refresh=True)
    assert "--full-refresh" in calls[0]
    runner_.freshness({})
    runner_.docs_generate({})
    with pytest.raises(DbtError, match="dbt test exited with 1"):
        runner_.test({})
    assert runner_.manifest_path().name == "manifest.json"
    assert runner_.run_results_path().name == "run_results.json"
    assert runner_.sources_path().name == "sources.json"


def test_git_sha_is_short_or_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    assert meta.git_sha() != ""
    monkeypatch.setattr("bank_data.reports.meta.shutil.which", lambda _: None)
    assert meta.git_sha() == "unknown"
    assert meta.generated_now().tzinfo is not None


def test_cli_codegen_check_version_and_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert runner.invoke(app, ["codegen", "--check"]).exit_code == 0
    assert "bank-data" in runner.invoke(app, ["version"]).output
    monkeypatch.setenv("BANK_DATA_DIR", str(tmp_path))
    result = runner.invoke(app, ["build", "--source", "sample"])
    assert result.exit_code == ConfigurationError.exit_code
    assert "run `bank-data ingest` first" in result.output
    assert runner.invoke(app, ["ingest", "--source", "local"]).exit_code == 2
    assert runner.invoke(app, ["report", "--source", "sample"]).exit_code == 2


def test_reports_from_non_s3_sources_never_overwrite_the_committed_docs(tmp_path: Path) -> None:
    sample = Workspace.resolve("sample", pipeline=_settings(tmp_path))
    organizer = Workspace.resolve("s3", pipeline=_settings(tmp_path))
    assert _report_path(sample, None, "quality-report.md") == tmp_path / "warehouse-sample" / "quality-report.md"
    assert _report_path(organizer, None, "quality-report.md") == REPOSITORY_ROOT / "docs" / "data" / "quality-report.md"
    assert _report_path(sample, tmp_path / "x.md", "lineage.md") == tmp_path / "x.md"
