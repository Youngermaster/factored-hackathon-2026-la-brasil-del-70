import secrets
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from bank_agent.adapters.persistence.postgres.budget import PostgresBudgetLedger
from bank_agent.adapters.persistence.postgres.readiness import PostgresReadinessCheck
from bank_agent.bootstrap.container import Container, application_database_url, budget_ledger
from bank_agent.bootstrap.settings import load_settings
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.degradation import Component, ComponentState
from bank_agent.domain.errors import ConfigurationError
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


def test_the_budget_ledger_is_shared_in_postgresql_only_with_a_database(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(env_file=None)
    assert budget_ledger(settings.llm, None) is None
    engine = create_async_engine("postgresql+asyncpg://bank_app@127.0.0.1:9/bank_agent")
    assert isinstance(budget_ledger(settings.llm, engine), PostgresBudgetLedger)
    monkeypatch.setenv("LLM_BUDGET_LEDGER", "memory")
    assert budget_ledger(load_settings(env_file=None).llm, engine) is None
    monkeypatch.setenv("LLM_BUDGET_LEDGER", "postgres")
    with pytest.raises(ConfigurationError, match="LLM_BUDGET_LEDGER"):
        budget_ledger(load_settings(env_file=None).llm, None)


def test_the_degradation_monitor_starts_at_l0_with_an_unconfigured_model() -> None:
    container = Container(load_settings(env_file=None))
    status = container.degradation.current()
    assert status.level.label == "L0"
    assert status.components[Component.LLM_PRIMARY] is ComponentState.DISABLED
    assert status.components[Component.DATABASE] is ComponentState.DISABLED
