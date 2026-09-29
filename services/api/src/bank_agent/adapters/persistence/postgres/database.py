"""The async engine and the only way to open a transaction: always with a database context.

``open_transaction`` sets ``app.role`` and ``app.customer_id`` with ``set_config(..., true)`` (local to the
transaction) before any other statement, so there is no code path that queries customer data without a context.
Database roles beyond the three access roles: ``identity`` (the identity service and the session store) and
``seed`` (the owner loading demo data).

Availability failures (a refused or dropped connection, a pool or statement timeout, a server shutting down, too many
connections, a read-only server) become ``DatabaseUnavailableError`` at the two places a transaction opens and ends:
here and in the unit of work. Other database errors keep their meaning (a constraint violation is a conflict).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import Final, Protocol

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError, InterfaceError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from bank_agent.domain.access import AccessContext
from bank_agent.domain.errors import DatabaseUnavailableError

LOCK_TIMEOUT = "2s"
UNAVAILABLE_SQLSTATES: Final = frozenset({"57P01", "57P02", "57P03", "53300", "25006"})
"""Admin or crash shutdown, cannot connect now, too many connections, read-only transaction; plus class 08."""


class AvailabilityListener(Protocol):
    """Told whether the database answered (the degradation monitor's ``DatabaseHealth``)."""

    def record(self, available: bool) -> None: ...


def _sqlstate(error: DBAPIError) -> str | None:
    for source in (error.orig, getattr(error.orig, "__cause__", None)):
        state = getattr(source, "sqlstate", None) or getattr(source, "pgcode", None)
        if isinstance(state, str):
            return state
    return None


def is_unavailable(error: BaseException) -> bool:
    """True for failures that mean the database cannot serve now, not that the request was wrong."""
    if isinstance(error, DatabaseUnavailableError | OSError | TimeoutError | PoolTimeoutError | InterfaceError):
        return True
    if isinstance(error, DBAPIError):
        if error.connection_invalidated:
            return True
        state = _sqlstate(error)
        return state is not None and (state.startswith("08") or state in UNAVAILABLE_SQLSTATES)
    return False


def unavailable(error: BaseException) -> DatabaseUnavailableError:
    """The domain error for ``error``, chained; the message names the failure type only, never its text."""
    if isinstance(error, DatabaseUnavailableError):
        return error
    translated = DatabaseUnavailableError(f"database unavailable ({type(error).__name__})")
    translated.__cause__ = error
    return translated


class DatabaseRole(StrEnum):
    """The value of ``app.role``: an access role, or one of the two service roles."""

    CUSTOMER = "customer"
    AGENT = "agent"
    EVALUATOR = "evaluator"
    IDENTITY = "identity"
    SEED = "seed"


def database_url(*, user: str, password: str | None, host: str, port: int, database: str) -> URL:
    return URL.create("postgresql+asyncpg", username=user, password=password, host=host, port=port, database=database)


def create_engine(url: URL, *, pooled: bool = True) -> AsyncEngine:
    """An asyncpg engine. ``pooled=False`` opens a connection per use (tests with one event loop per test)."""
    if pooled:
        return create_async_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
    return create_async_engine(url, poolclass=NullPool)


async def set_context(connection: AsyncConnection, role: DatabaseRole, customer_id: str | None) -> None:
    await connection.execute(
        text(
            "SELECT set_config('app.role', :role, true), set_config('app.customer_id', :customer, true), "
            "set_config('lock_timeout', :lock_timeout, true)"
        ),
        {"role": role.value, "customer": customer_id or "", "lock_timeout": LOCK_TIMEOUT},
    )


def role_of(context: AccessContext) -> DatabaseRole:
    return DatabaseRole(context.role.value)


@asynccontextmanager
async def open_transaction(
    engine: AsyncEngine, role: DatabaseRole, customer_id: str | None = None
) -> AsyncIterator[AsyncConnection]:
    """Yield a connection inside a transaction with the context set; commit on success, roll back on error."""
    try:
        async with engine.connect() as connection, connection.begin():
            await set_context(connection, role, customer_id)
            yield connection
    except Exception as error:
        if is_unavailable(error):
            raise unavailable(error) from error
        raise
