"""Composition root: the only module that knows concrete adapters.

The container turns settings into wired services. The HTTP layer consumes it through the
``bank_agent.api.provider.ServiceProvider`` Protocol, CLIs and the evaluation harness resolve from it
directly, and tests build it with their own settings. Later phases add repositories, the policy
evaluator, model clients, and port decorators here.
"""

from collections.abc import Sequence

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from bank_agent.adapters.persistence.postgres.readiness import PostgresReadinessCheck
from bank_agent.bootstrap.settings import AppSettings, DatabaseSettings
from bank_agent.ports.health import ReadinessCheck


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

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._engine: AsyncEngine | None = None
        if settings.database.is_configured:
            self._engine = create_async_engine(
                application_database_url(settings.database),
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
            )
        self._readiness_checks: tuple[ReadinessCheck, ...] = (
            (PostgresReadinessCheck(self._engine),) if self._engine is not None else ()
        )

    @property
    def readiness_checks(self) -> Sequence[ReadinessCheck]:
        return self._readiness_checks

    @property
    def database_engine(self) -> AsyncEngine | None:
        """The application-role engine, or ``None`` when no database is configured."""
        return self._engine

    async def aclose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
