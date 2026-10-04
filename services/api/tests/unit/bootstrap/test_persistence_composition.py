import secrets
from datetime import timedelta

import pytest

from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory
from bank_agent.adapters.persistence.postgres.rate_limits import PostgresRateLimitStore
from bank_agent.adapters.persistence.postgres.sessions import PostgresSessionStore
from bank_agent.adapters.persistence.postgres.unit_of_work import PostgresUnitOfWorkFactory
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.bootstrap.container import Container
from bank_agent.bootstrap.persistence import (
    build_persistence,
    build_rate_limit_store,
    conversation_creation_quota,
    owner_database_url,
    tools_with_failures,
)
from bank_agent.bootstrap.settings import load_settings
from bank_agent.domain.actions import ToolFailureMode, ToolName
from bank_agent.domain.conversation import DEFAULT_CONVERSATION_CREATION_QUOTA, ConversationCreationQuota
from bank_agent.domain.errors import ConfigurationError, ConversationCreationLimitedError
from bank_agent.domain.identifiers import CreditProductCode, PersonaId
from bank_agent.domain.identity import PersonaIdentification
from bank_agent_builders import conversation
from bank_agent_contracts import CONTEXT_A
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


async def test_the_configured_creation_quota_reaches_the_memory_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONVERSATION_CREATION_LIMIT", "1")
    monkeypatch.setenv("CONVERSATION_CREATION_WINDOW_MINUTES", "30")
    container = Container(load_settings(env_file=None))
    factory = container.persistence.uow_factory
    assert isinstance(factory, InMemoryUnitOfWorkFactory)
    assert factory.creation_quota == ConversationCreationQuota(limit=1, window=timedelta(minutes=30))
    async with factory(CONTEXT_A) as uow:
        await uow.conversations.add_with_quota(conversation("conv-quota-1"))
        await uow.commit()
    async with factory(CONTEXT_A) as uow:
        with pytest.raises(ConversationCreationLimitedError) as refused:
            await uow.conversations.add_with_quota(conversation("conv-quota-2"))
    assert refused.value.retry_after == timedelta(minutes=30)


async def test_the_configured_creation_quota_reaches_the_postgres_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", secrets.token_urlsafe(32))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("ALLOW_PUBLIC_DEMO_MODE", "true")
    settings = load_settings(env_file=None)
    container = Container(settings)
    factory = container.persistence.uow_factory
    assert isinstance(factory, PostgresUnitOfWorkFactory)
    assert factory.creation_quota == conversation_creation_quota(settings)
    assert factory.creation_quota == ConversationCreationQuota(limit=200, window=timedelta(hours=1))
    await container.aclose()


def test_injected_or_default_persistence_keeps_the_standard_quota() -> None:
    factory = build_persistence(None).uow_factory
    assert isinstance(factory, InMemoryUnitOfWorkFactory)
    assert factory.creation_quota == DEFAULT_CONVERSATION_CREATION_QUOTA
    assert ConversationCreationQuota(limit=5, window=timedelta(hours=1)) == DEFAULT_CONVERSATION_CREATION_QUOTA
