"""Persistence, identity, and banking tools, chosen from settings.

With the application role configured (``POSTGRES_APP_PASSWORD``) every store is PostgreSQL; otherwise the
in-memory adapters serve, empty, so the API still starts for local work without a database. The identity
provider needs ``SESSION_SECRET`` (its code and lookup keys derive from it) and is absent without one.
"""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine

from bank_agent.adapters.identity.codes import IdentityKeys
from bank_agent.adapters.identity.provider import MockIdentityProvider
from bank_agent.adapters.identity.sender import DemoOtpSender
from bank_agent.adapters.identity.store import ChallengeStore, InMemoryChallengeStore
from bank_agent.adapters.persistence.duckdb.gold import DATASET_CREDIT_BALANCE_CONVENTION
from bank_agent.adapters.persistence.memory.sessions import InMemorySessionStore
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory, standalone_audit_log
from bank_agent.adapters.persistence.postgres.audit import PostgresStandaloneAuditLog
from bank_agent.adapters.persistence.postgres.challenges import PostgresChallengeStore
from bank_agent.adapters.persistence.postgres.database import AvailabilityListener, database_url
from bank_agent.adapters.persistence.postgres.rate_limits import PostgresRateLimitStore, rate_limit_key
from bank_agent.adapters.persistence.postgres.sessions import PostgresSessionStore
from bank_agent.adapters.persistence.postgres.unit_of_work import PostgresUnitOfWorkFactory
from bank_agent.application.identity.sessions import SessionService
from bank_agent.application.tools.banking import BankingTools, SessionToolset
from bank_agent.application.tools.base import ToolDependencies
from bank_agent.application.tools.context import SessionContext, ToolPolicy, ToolSettings
from bank_agent.application.tools.failure_injection import ToolFailureInjector
from bank_agent.bootstrap.settings import AppSettings, DatabaseSettings
from bank_agent.domain.actions import ToolFailureMode, ToolName
from bank_agent.domain.conversation import DEFAULT_CONVERSATION_CREATION_QUOTA, ConversationCreationQuota
from bank_agent.domain.errors import ConfigurationError
from bank_agent.ports.audit import AuditLog
from bank_agent.ports.credit_catalog import CreditProductCatalog
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.rate_limits import RateLimitStore
from bank_agent.ports.sessions import SessionStore
from bank_agent.ports.unit_of_work import UnitOfWorkFactory


def owner_database_url(database: DatabaseSettings) -> URL:
    """The owner role's URL, for migrations and the seed. Its string form masks the password."""
    password = database.admin_password.get_secret_value() if database.admin_password is not None else None
    return database_url(
        user=database.admin_user, password=password, host=database.host, port=database.port, database=database.db
    )


@dataclass(frozen=True)
class PersistenceServices:
    uow_factory: UnitOfWorkFactory
    session_store: SessionStore
    audit_log: AuditLog
    challenge_store: ChallengeStore


def conversation_creation_quota(settings: AppSettings) -> ConversationCreationQuota:
    """The new-chat quota from ``CONVERSATION_CREATION_*``, with the public demo's higher default when it applies."""
    conversation = settings.conversation
    return ConversationCreationQuota(
        limit=conversation.creation_limit_for(settings.runtime),
        window=timedelta(minutes=conversation.creation_window_minutes),
    )


def build_persistence(
    engine: AsyncEngine | None,
    listener: AvailabilityListener | None = None,
    *,
    creation_quota: ConversationCreationQuota = DEFAULT_CONVERSATION_CREATION_QUOTA,
) -> PersistenceServices:
    """PostgreSQL when ``engine`` is given (``listener`` hears whether each transaction reached the database).

    ``creation_quota`` bounds new chats per customer in both backends.
    """
    if engine is not None:
        return PersistenceServices(
            uow_factory=PostgresUnitOfWorkFactory(engine, listener, creation_quota=creation_quota),
            session_store=PostgresSessionStore(engine),
            audit_log=PostgresStandaloneAuditLog(engine),
            challenge_store=PostgresChallengeStore(engine),
        )
    store = InMemoryStore()
    return PersistenceServices(
        uow_factory=InMemoryUnitOfWorkFactory(store, creation_quota=creation_quota),
        session_store=InMemorySessionStore(),
        audit_log=standalone_audit_log(store),
        challenge_store=InMemoryChallengeStore(),
    )


def build_rate_limit_store(settings: AppSettings, engine: AsyncEngine | None, clock: Clock) -> RateLimitStore | None:
    """The shared PostgreSQL store with ``RATE_LIMIT_BACKEND=postgres``; ``None`` keeps the counters in the process."""
    if settings.security.rate_limit_backend == "memory":
        return None
    secret = settings.security.session_secret
    if engine is None or secret is None or not secret.get_secret_value().strip():
        raise ConfigurationError("RATE_LIMIT_BACKEND=postgres needs the database settings and SESSION_SECRET")
    return PostgresRateLimitStore(engine, clock, rate_limit_key(secret.get_secret_value().encode("utf-8")))


def build_session_service(
    settings: AppSettings, persistence: PersistenceServices, *, clock: Clock, ids: IdGenerator
) -> SessionService | None:
    secret = settings.security.session_secret
    if secret is None or not secret.get_secret_value().strip():
        return None
    provider = MockIdentityProvider(
        store=persistence.challenge_store,
        sender=DemoOtpSender(demo_mode=settings.runtime.demo_mode),
        keys=IdentityKeys(secret.get_secret_value().encode("utf-8")),
        clock=clock,
        ids=ids,
    )
    return SessionService(
        identity=provider, store=persistence.session_store, audit=persistence.audit_log, clock=clock, ids=ids
    )


def build_banking_tools(
    persistence: PersistenceServices,
    *,
    clock: Clock,
    ids: IdGenerator,
    catalog: CreditProductCatalog,
    tool_policy: ToolPolicy,
) -> BankingTools:
    """The banking tools over the synthetic catalog, with their policy parameters from the pack."""
    return BankingTools(
        ToolDependencies(
            uow_factory=persistence.uow_factory,
            catalog=catalog,
            clock=clock,
            ids=ids,
            settings=ToolSettings(policy=tool_policy, balance_convention=DATASET_CREDIT_BALANCE_CONVENTION),
        )
    )


def tools_with_failures(
    settings: AppSettings, tools: BankingTools, context: SessionContext, plan: dict[ToolName, ToolFailureMode]
) -> SessionToolset:
    """Session tools wrapped in the failure injector, for tests and evaluations. Refused in production."""
    return ToolFailureInjector(
        tools.for_session(context),
        tools.for_session(context, commit=False),
        plan,
        environment=settings.runtime.app_env,
    )
