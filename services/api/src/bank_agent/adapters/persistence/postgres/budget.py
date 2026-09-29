"""``PostgresBudgetLedger``: the model budget counters in ``app.llm_budget``, shared by every API process.

A reservation runs in one transaction: it makes sure the scope's rows exist, locks them in a fixed order (so two
processes never deadlock), checks every cap against the locked values, and adds to all of them or to none. A settle
adjusts the same rows and never lets a counter go below zero. Availability failures become
``DatabaseUnavailableError``; the budget guard then refuses the model call (fail closed).
"""

from decimal import Decimal
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from bank_agent.adapters.llm.budget import first_refusal
from bank_agent.adapters.persistence.postgres.database import is_unavailable, unavailable
from bank_agent.ports.budget import BudgetLimits, BudgetScope, Reservation

_ENSURE: Final = (
    "INSERT INTO app.llm_budget (scope, scope_key) VALUES (:scope, :scope_key) "
    "ON CONFLICT (scope, scope_key) DO NOTHING"
)
_LOCK: Final = (
    "SELECT scope, scope_key, tokens, cost_usd FROM app.llm_budget "
    "WHERE (scope, scope_key) IN (SELECT * FROM unnest(CAST(:scopes AS text[]), CAST(:keys AS text[]))) "
    "ORDER BY scope, scope_key FOR UPDATE"
)
_ADD: Final = (
    "UPDATE app.llm_budget SET tokens = GREATEST(0, tokens + :tokens), "
    "cost_usd = GREATEST(0, cost_usd + :cost), updated_at = now() WHERE scope = :scope AND scope_key = :scope_key"
)


def _rows(scope: BudgetScope) -> list[tuple[str, str]]:
    rows = [("day", scope.day.isoformat())]
    if scope.session is not None:
        rows.append(("session", scope.session))
    if scope.conversation is not None:
        rows.append(("conversation", scope.conversation))
    return sorted(rows)


class PostgresBudgetLedger:
    """Implements ``BudgetLedger`` over the application-role engine."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def _locked(self, connection: AsyncConnection, scope: BudgetScope) -> dict[str, tuple[int, Decimal]]:
        rows = _rows(scope)
        for kind, key in rows:
            await connection.execute(text(_ENSURE), {"scope": kind, "scope_key": key})
        result = await connection.execute(
            text(_LOCK), {"scopes": [kind for kind, _ in rows], "keys": [key for _, key in rows]}
        )
        return {str(row.scope): (int(row.tokens), Decimal(row.cost_usd)) for row in result}

    async def _add(self, connection: AsyncConnection, scope: BudgetScope, tokens: int, cost: Decimal) -> None:
        for kind, key in _rows(scope):
            await connection.execute(text(_ADD), {"tokens": tokens, "cost": cost, "scope": kind, "scope_key": key})

    async def reserve(self, scope: BudgetScope, *, tokens: int, cost: Decimal, limits: BudgetLimits) -> Reservation:
        try:
            async with self._engine.begin() as connection:
                counters = await self._locked(connection, scope)
                session_tokens = counters.get("session", (0, Decimal(0)))[0]
                conversation_cost = counters.get("conversation", (0, Decimal(0)))[1]
                daily = counters["day"][1]
                refused = first_refusal(
                    limits,
                    session_tokens=session_tokens + tokens,
                    conversation_cost=conversation_cost + cost,
                    daily_cost=daily + cost,
                    scope=scope,
                )
                if refused is not None:
                    return Reservation(refused_by=refused, daily_spent_usd=daily)
                await self._add(connection, scope, tokens, cost)
                return Reservation(refused_by=None, daily_spent_usd=daily + cost)
        except Exception as error:
            if is_unavailable(error):
                raise unavailable(error) from error
            raise

    async def settle(self, scope: BudgetScope, *, tokens: int, cost: Decimal) -> Decimal:
        try:
            async with self._engine.begin() as connection:
                await self._locked(connection, scope)
                await self._add(connection, scope, tokens, cost)
                daily = await connection.execute(
                    text("SELECT cost_usd FROM app.llm_budget WHERE scope = 'day' AND scope_key = :key"),
                    {"key": scope.day.isoformat()},
                )
                return Decimal(daily.scalar_one())
        except Exception as error:
            if is_unavailable(error):
                raise unavailable(error) from error
            raise
