"""Chaos and failure-injection support: a database outage and a slow table on the real PostgreSQL container, a tool
provider that cuts the database just before a write, and helpers that read the evaluator trace. Test doubles only."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bank_agent.application.tools.banking import BankingTools, EngineOnlyTools, SessionToolset
from bank_agent.application.tools.base import ToolDependencies
from bank_agent.application.tools.context import SessionContext
from bank_agent.domain.actions import WRITE_TOOLS
from bank_agent_api import ApiClient

LIMITED_ES = "En este momento funciono en modo limitado"
LIMITED_PT = "No momento estou funcionando em modo limitado"


class DatabaseOutage:
    """Cuts the application role off PostgreSQL: no new connection (connection limit 0, SQLSTATE 53300) and every
    open one terminated; or, with ``read_only``, new sessions only read (SQLSTATE 25006 on a write)."""

    def __init__(self, owner: AsyncEngine, app_user: str) -> None:
        self._owner = owner
        self._app_user = app_user

    async def _terminate(self) -> None:
        async with self._owner.begin() as connection:
            await connection.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = :user"),
                {"user": self._app_user},
            )

    async def begin(self, *, read_only: bool = False) -> None:
        setting = "SET default_transaction_read_only = on" if read_only else "CONNECTION LIMIT 0"
        async with self._owner.begin() as connection:
            await connection.execute(text(f"ALTER ROLE {self._app_user} {setting}"))  # nosec B608 (fixture role)
        await self._terminate()

    async def end(self) -> None:
        async with self._owner.begin() as connection:
            await connection.execute(text(f"ALTER ROLE {self._app_user} CONNECTION LIMIT -1"))  # nosec B608
            await connection.execute(text(f"ALTER ROLE {self._app_user} RESET default_transaction_read_only"))  # nosec B608
        await self._terminate()

    @asynccontextmanager
    async def during(self, *, read_only: bool = False) -> AsyncIterator[None]:
        await self.begin(read_only=read_only)
        try:
            yield
        finally:
            await self.end()


@asynccontextmanager
async def slow_table(owner: AsyncEngine, table: str) -> AsyncIterator[None]:
    """Hold an exclusive lock on ``app.<table>`` so every read of it waits: a slow database, from the tool's side."""
    async with owner.connect() as connection:
        transaction = await connection.begin()
        await connection.execute(text(f"LOCK TABLE app.{table} IN ACCESS EXCLUSIVE MODE"))  # nosec B608
        try:
            yield
        finally:
            await transaction.rollback()


class _CutBeforeWrite:
    """A session toolset that runs ``before`` once, right before the first write tool, then delegates."""

    def __init__(self, inner: SessionToolset, before: Callable[[], Awaitable[None]]) -> None:
        self._inner = inner
        self._before = before

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if name not in {tool.value for tool in WRITE_TOOLS} or not callable(attribute):
            return attribute

        async def guarded(*args: Any, **kwargs: Any) -> Any:
            await self._before()
            return await attribute(*args, **kwargs)

        return guarded


class OutageBeforeWrite:
    """A ``ToolProvider`` whose write tools find the database gone: the outage starts mid-turn, after every read."""

    def __init__(self, tools: BankingTools, outage: DatabaseOutage) -> None:
        self._tools = tools
        self._outage = outage
        self.triggered = False

    async def _cut(self) -> None:
        if not self.triggered:
            self.triggered = True
            await self._outage.begin()

    def for_session(self, context: SessionContext) -> SessionToolset:
        return cast(SessionToolset, _CutBeforeWrite(self._tools.for_session(context), self._cut))

    def engine_only(self, context: SessionContext) -> EngineOnlyTools:
        return self._tools.engine_only(context)

    @property
    def dependencies(self) -> ToolDependencies:
        return self._tools.dependencies


async def staff_records(client: ApiClient, conversation: str) -> dict[str, dict[str, Any]]:
    """The evaluator trace of ``conversation`` by turn id: every execution record, safety interventions included."""
    await client.login("persona-evaluator")
    response = await client.get(f"/v1/eval/conversations/{conversation}/trace")
    assert response.status_code == 200, response.text
    return {str(record["turn_id"]): record for record in response.json()["records"]}


async def settle() -> None:
    """Let terminated backends finish before the next connection attempt."""
    await asyncio.sleep(0.05)
