import secrets

import pytest

from bank_agent.adapters.persistence.postgres.readiness import PostgresReadinessCheck
from bank_agent.bootstrap.container import Container, application_database_url
from bank_agent.bootstrap.settings import load_settings


def test_no_readiness_checks_without_a_database() -> None:
    container = Container(load_settings(env_file=None))

    assert container.readiness_checks == ()
    assert container.database_engine is None


async def test_database_settings_add_a_postgres_readiness_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", secrets.token_urlsafe(32))
    container = Container(load_settings(env_file=None))

    (check,) = container.readiness_checks
    assert isinstance(check, PostgresReadinessCheck)
    assert check.name == "database"
    assert container.database_engine is not None
    await container.aclose()


async def test_closing_without_a_database_is_a_no_op() -> None:
    await Container(load_settings(env_file=None)).aclose()


def test_database_url_uses_the_application_role_and_masks_the_password(monkeypatch: pytest.MonkeyPatch) -> None:
    password = secrets.token_urlsafe(32)
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", password)
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "6543")

    url = application_database_url(load_settings(env_file=None).database)

    assert url.drivername == "postgresql+asyncpg"
    assert url.username == "bank_app"
    assert url.host == "db.internal"
    assert url.port == 6543
    assert url.database == "bank_agent"
    assert url.password == password
    assert password not in str(url)
    assert password not in repr(url)
