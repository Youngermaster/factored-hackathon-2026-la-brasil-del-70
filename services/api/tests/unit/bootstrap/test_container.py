import secrets
from datetime import date

import pytest

from bank_agent.adapters.persistence.postgres.readiness import PostgresReadinessCheck
from bank_agent.bootstrap.container import Container, application_database_url
from bank_agent.bootstrap.settings import load_settings
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.locale import Country


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


def test_the_container_loads_the_policy_pack_catalog_and_tool_parameters() -> None:
    container = Container(load_settings(env_file=None))
    policy = container.policy
    assert policy.data_as_of == date(2026, 6, 17)
    assert policy.pack.pack_version().startswith("pack-")
    assert str(policy.eligibility.service) == f"eligibility:synthetic@{policy.pack.version}"
    assert policy.tool_policy.max_statement_days == 92
    assert policy.tool_policy.dispute_sla_days == {Country.MX: 45, Country.CO: 15, Country.AR: 30}
    assert policy.tool_policy.step_up_actions == frozenset(ActionKind)
    assert {p.product_code for p in policy.catalog.list(Country.CO)} >= {"CO-PL-STANDARD"}
    assert container.banking_tools.dependencies.settings.policy is policy.tool_policy


def test_policy_settings_read_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLICY_DATA_AS_OF", "2026-06-30")
    monkeypatch.setenv("POLICY_DIR", "")
    settings = load_settings(env_file=None)
    assert settings.policy.data_as_of == date(2026, 6, 30)
    assert settings.policy.dir.name == "policies"
