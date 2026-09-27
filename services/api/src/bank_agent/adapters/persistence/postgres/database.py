"""The async engine and the only way to open a transaction: always with a database context.

``open_transaction`` sets ``app.role`` and ``app.customer_id`` with ``set_config(..., true)`` (local to the
transaction) before any other statement, so there is no code path that queries customer data without a context.
Database roles beyond the three access roles: ``identity`` (the identity service and the session store) and
``seed`` (the owner loading demo data).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from bank_agent.domain.access import AccessContext

LOCK_TIMEOUT = "2s"


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
    async with engine.connect() as connection, connection.begin():
        await set_context(connection, role, customer_id)
        yield connection
