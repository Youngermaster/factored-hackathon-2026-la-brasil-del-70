"""One open PostgreSQL transaction bound to an access context, shared by the repositories of a unit of work.

Every statement goes through ``Tx``: bound parameters only, rows returned as mappings. Writes that meet a row
locked by another open transaction do not wait: ``lock_or_mark_conflicted`` marks the transaction conflicted,
and the unit of work's ``commit`` then raises ``ConcurrencyConflictError`` and applies nothing. This mirrors
the optimistic behavior of the in-memory unit of work and never blocks a request on another request's lock.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from bank_agent.domain.access import AccessContext
from bank_agent.domain.errors import AccessContextError

LOCK_NOT_AVAILABLE = "55P03"
UNIQUE_VIOLATION = "23505"
INSUFFICIENT_PRIVILEGE = "42501"

Row = Mapping[str, Any]


def sqlstate(error: BaseException) -> str | None:
    """The PostgreSQL SQLSTATE behind a SQLAlchemy or asyncpg error, if any."""
    candidates: list[object] = [error, getattr(error, "orig", None)]
    orig = getattr(error, "orig", None)
    if orig is not None:
        candidates.append(getattr(orig, "__cause__", None))
    for candidate in candidates:
        code = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)
        if isinstance(code, str):
            return code
    return None


def constraint_name(error: BaseException) -> str | None:
    orig = getattr(error, "orig", None)
    for candidate in (orig, getattr(orig, "__cause__", None)):
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str):
            return name
    return None


class Tx:
    """The connection of one transaction plus its context and conflict flag."""

    def __init__(self, connection: AsyncConnection, context: AccessContext | None = None) -> None:
        self.connection = connection
        self._context = context
        self.conflicted = False

    @property
    def context(self) -> AccessContext:
        """The access context. Service transactions (identity, seed) have none and cannot use repositories."""
        if self._context is None:
            raise AccessContextError("this transaction has no access context")
        return self._context

    async def rows(self, sql: str, parameters: Mapping[str, object] | None = None) -> Sequence[Row]:
        result = await self.connection.execute(text(sql), dict(parameters or {}))
        return [dict(row._mapping) for row in result]

    async def one_or_none(self, sql: str, parameters: Mapping[str, object] | None = None) -> Row | None:
        found = await self.rows(sql, parameters)
        return found[0] if found else None

    async def scalar(self, sql: str, parameters: Mapping[str, object] | None = None) -> object:
        result = await self.connection.execute(text(sql), dict(parameters or {}))
        return result.scalar()

    async def execute(self, sql: str, parameters: Mapping[str, object] | None = None) -> int:
        """Run a write and return the number of affected rows."""
        result = await self.connection.execute(text(sql), dict(parameters or {}))
        return int(result.rowcount)

    async def guarded(self, sql: str, parameters: Mapping[str, object] | None = None) -> int:
        """Run a write inside a savepoint, so a constraint error leaves the transaction usable."""
        async with self.connection.begin_nested():
            return await self.execute(sql, parameters)

    async def lock_or_mark_conflicted(self, sql: str, parameters: Mapping[str, object]) -> bool:
        """Run a ``SELECT ... FOR NO KEY UPDATE NOWAIT``. Return False (and mark the transaction conflicted) when
        another open transaction holds the row."""
        try:
            async with self.connection.begin_nested():
                await self.connection.execute(text(sql), dict(parameters))
        except DBAPIError as error:
            if sqlstate(error) != LOCK_NOT_AVAILABLE:
                raise
            self.conflicted = True
            return False
        return True
