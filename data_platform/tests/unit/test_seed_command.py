import secrets
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bank_agent.bootstrap.settings import load_settings
from bank_data.cli import app
from bank_data.errors import ConfigurationError
from bank_data.seed.command import seed
from bank_data.seed.config import load_personas
from bank_data.seed.criteria import CRITERIA
from bank_data.workspace import Workspace


def test_the_committed_personas_cover_every_workflow_and_name_known_criteria() -> None:
    personas = load_personas()
    assert {persona.criterion for persona in personas.customers} <= set(CRITERIA)
    covered = {workflow for persona in personas.customers for workflow in persona.workflows}
    assert covered == {"account_inquiry", "card_support", "dispute", "credit"}
    for country in ("MX", "CO", "AR"):
        assert sum(persona.country == country for persona in personas.customers) >= 2
    assert {item.role for item in personas.staff} == {"agent", "evaluator"}
    assert sum(persona.seeded_case for persona in personas.customers) == 1
    assert sum(persona.seeded_application for persona in personas.customers) == 1


def test_seeding_needs_gold_tables(tmp_path: Path) -> None:
    workspace = Workspace.resolve("sample", warehouse_dir=tmp_path)
    with pytest.raises(ConfigurationError, match="run make pipeline first"):
        seed(workspace, settings=load_settings(env_file=None))


def test_seeding_names_the_missing_settings_without_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("POSTGRES_ADMIN_PASSWORD", "SESSION_SECRET"):
        monkeypatch.delenv(name, raising=False)
    workspace = Workspace.resolve("sample", warehouse_dir=tmp_path)
    gold = workspace.dbt_target().gold_dir
    gold.mkdir(parents=True)
    (gold / "customers_serving.parquet").write_bytes(b"")
    with pytest.raises(ConfigurationError, match="POSTGRES_ADMIN_PASSWORD, SESSION_SECRET"):
        seed(workspace, settings=load_settings(env_file=None))
    monkeypatch.setenv("POSTGRES_ADMIN_PASSWORD", secrets.token_urlsafe(24))
    monkeypatch.setenv("SESSION_SECRET", "short")
    with pytest.raises(ConfigurationError, match="at least 32 bytes"):
        seed(workspace, settings=load_settings(env_file=None))


def test_the_cli_reports_configuration_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BANK_DATA_WAREHOUSE_DIR", str(tmp_path))
    result = CliRunner().invoke(app, ["seed", "--source", "sample", "--customers", "5"])
    assert result.exit_code == 2
    assert "run make pipeline first" in result.output
