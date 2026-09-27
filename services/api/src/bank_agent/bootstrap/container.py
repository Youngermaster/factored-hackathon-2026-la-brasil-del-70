"""Composition root: the only module that knows concrete adapters.

The container turns settings into wired services. The HTTP layer consumes it through the
``bank_agent.api.provider.ServiceProvider`` Protocol, CLIs and the evaluation harness resolve from it
directly, and tests build it with their own settings. The language model gateway is built here from settings
(``bootstrap/llm.py``); tests and the evaluation harness inject a base client through ``LlmOverrides``. Later
phases add the policy evaluator and model clients here. Persistence, identity, and the banking tools come from
``bootstrap/persistence.py``.
"""

from collections.abc import Sequence

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from bank_agent.adapters.persistence.postgres.readiness import PostgresReadinessCheck
from bank_agent.adapters.prompts.file_registry import FilePromptRegistry
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.adapters.system.ids import RandomIdGenerator
from bank_agent.adapters.telemetry.noop import NoopTelemetry
from bank_agent.application.identity.sessions import SessionService
from bank_agent.application.tools.banking import BankingTools
from bank_agent.bootstrap.llm import LlmOverrides, build_llm_client
from bank_agent.bootstrap.persistence import (
    PersistenceServices,
    build_banking_tools,
    build_persistence,
    build_session_service,
)
from bank_agent.bootstrap.settings import AppSettings, DatabaseSettings
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.health import ReadinessCheck
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.prompts import PromptRegistry
from bank_agent.ports.telemetry import Telemetry


def application_database_url(database: DatabaseSettings) -> URL:
    """Connection URL for the application role. Its string form masks the password."""
    password = database.app_password.get_secret_value() if database.app_password is not None else None
    return URL.create(
        drivername="postgresql+asyncpg",
        username=database.app_user,
        password=password,
        host=database.host,
        port=database.port,
        database=database.db,
    )


class Container:
    """Wired services for one process. Satisfies ``ServiceProvider`` structurally."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        clock: Clock | None = None,
        telemetry: Telemetry | None = None,
        llm_overrides: LlmOverrides | None = None,
        ids: IdGenerator | None = None,
    ) -> None:
        self.settings = settings
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._telemetry: Telemetry = telemetry if telemetry is not None else NoopTelemetry()
        self._prompt_registry = FilePromptRegistry.from_package()
        self._llm_client = build_llm_client(
            settings.llm,
            registry=self._prompt_registry,
            clock=self._clock,
            telemetry=self._telemetry,
            overrides=llm_overrides,
        )
        self._engine: AsyncEngine | None = None
        if settings.database.is_configured:
            self._engine = create_async_engine(
                application_database_url(settings.database),
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
            )
        self._ids: IdGenerator = ids if ids is not None else RandomIdGenerator()
        self._persistence = build_persistence(self._engine)
        self._session_service = build_session_service(settings, self._persistence, clock=self._clock, ids=self._ids)
        self._banking_tools = build_banking_tools(self._persistence, clock=self._clock, ids=self._ids)
        self._readiness_checks: tuple[ReadinessCheck, ...] = (
            (PostgresReadinessCheck(self._engine),) if self._engine is not None else ()
        )

    @property
    def readiness_checks(self) -> Sequence[ReadinessCheck]:
        return self._readiness_checks

    @property
    def clock(self) -> Clock:
        return self._clock

    @property
    def telemetry(self) -> Telemetry:
        return self._telemetry

    @property
    def prompt_registry(self) -> PromptRegistry:
        return self._prompt_registry

    @property
    def llm_client(self) -> LLMClient:
        """The fully decorated language model gateway."""
        return self._llm_client

    @property
    def persistence(self) -> PersistenceServices:
        """The unit of work factory, session store, audit log, and challenge store (PostgreSQL or memory)."""
        return self._persistence

    @property
    def session_service(self) -> SessionService | None:
        """Login, step-up, and sessions; ``None`` until ``SESSION_SECRET`` is set."""
        return self._session_service

    @property
    def banking_tools(self) -> BankingTools:
        return self._banking_tools

    @property
    def database_engine(self) -> AsyncEngine | None:
        """The application-role engine, or ``None`` when no database is configured."""
        return self._engine

    async def aclose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
