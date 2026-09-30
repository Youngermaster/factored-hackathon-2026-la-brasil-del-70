import secrets

import pytest

from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory
from bank_agent.adapters.persistence.postgres.rate_limits import PostgresRateLimitStore
from bank_agent.adapters.persistence.postgres.sessions import PostgresSessionStore
from bank_agent.adapters.persistence.postgres.unit_of_work import PostgresUnitOfWorkFactory
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.bootstrap.container import Container
from bank_agent.bootstrap.persistence import build_rate_limit_store, owner_database_url, tools_with_failures
from bank_agent.bootstrap.settings import load_settings
from bank_agent.domain.actions import ToolFailureMode, ToolName
from bank_agent.domain.errors import ConfigurationError
from bank_agent.domain.identifiers import CreditProductCode, PersonaId
from bank_agent.domain.identity import PersonaIdentification
from bank_agent_tools import session_context


def test_without_a_database_the_memory_adapters_serve_and_identity_needs_a_secret() -> None:
    container = Container(load_settings(env_file=None))
    assert isinstance(container.persistence.uow_factory, InMemoryUnitOfWorkFactory)
    assert container.session_service is None
    catalog = container.banking_tools.dependencies.catalog
    assert catalog is container.policy.catalog
    assert catalog.get(CreditProductCode("CO-PL-STANDARD")) is not None


async def test_database_settings_select_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", secrets.token_urlsafe(32))
    container = Container(load_settings(env_file=None))
    assert isinstance(container.persistence.uow_factory, PostgresUnitOfWorkFactory)
    assert isinstance(container.persistence.session_store, PostgresSessionStore)
    await container.aclose()


async def test_a_session_secret_enables_the_identity_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("DEMO_MODE", "true")
    container = Container(load_settings(env_file=None))
    assert container.session_service is not None
    challenge = await container.session_service.start_login(PersonaIdentification(persona_id=PersonaId("nobody")))
    assert challenge.delivery.channel == "demo"


def test_the_owner_url_masks_the_password(monkeypatch: pytest.MonkeyPatch) -> None:
    password = secrets.token_urlsafe(32)
    monkeypatch.setenv("POSTGRES_ADMIN_PASSWORD", password)
    url = owner_database_url(load_settings(env_file=None).database)
    assert url.username == "bank_owner"
    assert password not in str(url)


def test_the_failure_injector_is_refused_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    container = Container(load_settings(env_file=None))
    plan = {ToolName.BLOCK_CARD: ToolFailureMode.PARTIAL_WRITE}
    assert tools_with_failures(container.settings, container.banking_tools, session_context(), plan) is not None
    container.settings.runtime.app_env = "production"
    with pytest.raises(ConfigurationError):
        tools_with_failures(container.settings, container.banking_tools, session_context(), plan)


def test_the_rate_limit_store_is_in_process_unless_the_shared_backend_is_chosen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert build_rate_limit_store(load_settings(env_file=None), None, SystemClock()) is None
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "postgres")
    with pytest.raises(ConfigurationError, match="RATE_LIMIT_BACKEND=postgres"):
        build_rate_limit_store(load_settings(env_file=None), None, SystemClock())


async def test_the_shared_backend_builds_the_postgres_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "postgres")
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", secrets.token_urlsafe(32))
    monkeypatch.setenv("SESSION_SECRET", secrets.token_urlsafe(48))
    container = Container(load_settings(env_file=None))
    assert isinstance(container.rate_limit_store, PostgresRateLimitStore)
    assert "SESSION_SECRET" not in repr(container.rate_limit_store)
    await container.aclose()
