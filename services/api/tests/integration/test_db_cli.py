import pytest
from typer.testing import CliRunner

from bank_agent.adapters.persistence.postgres import migrate
from bank_agent.cli import app
from bank_agent_test_support import PostgresInstance


def test_db_upgrade_brings_the_schema_to_head(
    migrated_postgres: PostgresInstance, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POSTGRES_HOST", migrated_postgres.host)
    monkeypatch.setenv("POSTGRES_PORT", str(migrated_postgres.port))
    monkeypatch.setenv("POSTGRES_DB", migrated_postgres.database)
    monkeypatch.setenv("POSTGRES_ADMIN_USER", migrated_postgres.owner)
    monkeypatch.setenv("POSTGRES_ADMIN_PASSWORD", migrated_postgres.owner_password)
    monkeypatch.setenv("POSTGRES_APP_USER", migrated_postgres.app_user)

    result = CliRunner().invoke(app, ["db", "upgrade"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"schema at revision {migrate.head_revision()}"
