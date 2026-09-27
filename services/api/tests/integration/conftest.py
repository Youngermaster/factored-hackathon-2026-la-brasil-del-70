"""Integration fixtures. The ``postgres`` and ``migrated_postgres`` session fixtures live in
``bank_agent_postgres`` and are registered by the repository root ``conftest.py``."""

import pytest

from bank_agent_test_support import PostgresInstance


@pytest.fixture
def database_environment(postgres: PostgresInstance, monkeypatch: pytest.MonkeyPatch) -> PostgresInstance:
    """Point the settings at the test database, connecting as the application role."""
    monkeypatch.setenv("POSTGRES_HOST", postgres.host)
    monkeypatch.setenv("POSTGRES_PORT", str(postgres.port))
    monkeypatch.setenv("POSTGRES_DB", postgres.database)
    monkeypatch.setenv("POSTGRES_APP_USER", postgres.app_user)
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", postgres.app_password)
    return postgres
