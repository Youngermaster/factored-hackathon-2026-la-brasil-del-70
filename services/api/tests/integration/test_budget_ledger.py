"""The budget ledger contract on memory and PostgreSQL, and the shared ledger under concurrent reservations."""

import asyncio
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest

from bank_agent.adapters.llm.budget import InMemoryBudgetLedger
from bank_agent.adapters.persistence.postgres.budget import PostgresBudgetLedger
from bank_agent.adapters.persistence.postgres.database import create_engine, database_url
from bank_agent.domain.errors import DatabaseUnavailableError
from bank_agent.ports.budget import BudgetCap, BudgetLedger, BudgetLimits, BudgetScope
from bank_agent_postgres import app_engine, reset_database
from bank_agent_test_support import PostgresInstance

DAY = date(2026, 9, 26)
LIMITS = BudgetLimits(session_token_limit=1000, conversation_cost_limit_usd=Decimal("0.05"),
                      daily_cost_limit_usd=Decimal("0.10"))  # fmt: skip
SCOPE = BudgetScope(session="lin-1", conversation="conv-1", day=DAY)


@pytest.fixture(params=["memory", "postgres"])
async def ledger(request: pytest.FixtureRequest) -> AsyncIterator[BudgetLedger]:
    if request.param == "memory":
        yield InMemoryBudgetLedger()
        return
    instance: PostgresInstance = request.getfixturevalue("migrated_postgres")
    await reset_database(instance)
    engine = app_engine(instance)
    try:
        yield PostgresBudgetLedger(engine)
    finally:
        await engine.dispose()


async def test_a_reservation_charges_every_counter_of_its_scope(ledger: BudgetLedger) -> None:
    reservation = await ledger.reserve(SCOPE, tokens=400, cost=Decimal("0.02"), limits=LIMITS)
    assert (reservation.refused_by, reservation.daily_spent_usd) == (None, Decimal("0.02"))
    other = BudgetScope(session=None, conversation=None, day=DAY)
    assert (await ledger.reserve(other, tokens=1, cost=Decimal("0.01"), limits=LIMITS)).daily_spent_usd == Decimal(
        "0.03"
    )


@pytest.mark.parametrize(
    ("tokens", "cost", "cap"),
    [(1001, Decimal(0), BudgetCap.SESSION_TOKENS), (1, Decimal("0.06"), BudgetCap.CONVERSATION_COST)],
)
async def test_a_refused_reservation_names_its_cap_and_adds_nothing(
    ledger: BudgetLedger, tokens: int, cost: Decimal, cap: BudgetCap
) -> None:
    refused = await ledger.reserve(SCOPE, tokens=tokens, cost=cost, limits=LIMITS)
    assert (refused.refused_by, refused.daily_spent_usd) == (cap, Decimal(0))
    assert (await ledger.reserve(SCOPE, tokens=1000, cost=Decimal("0.05"), limits=LIMITS)).refused_by is None


async def test_the_daily_cap_spans_conversations_and_settles_never_go_negative(ledger: BudgetLedger) -> None:
    for index in range(2):
        scope = BudgetScope(session=f"lin-{index}", conversation=f"conv-{index}", day=DAY)
        assert (await ledger.reserve(scope, tokens=10, cost=Decimal("0.05"), limits=LIMITS)).refused_by is None
    third = BudgetScope(session="lin-3", conversation="conv-3", day=DAY)
    assert (await ledger.reserve(third, tokens=10, cost=Decimal("0.01"), limits=LIMITS)).refused_by is (
        BudgetCap.DAILY_COST
    )
    assert await ledger.settle(third, tokens=-50, cost=Decimal("-0.30")) == Decimal(0)


async def test_concurrent_reservations_in_the_shared_ledger_never_overspend(
    migrated_postgres: PostgresInstance,
) -> None:
    await reset_database(migrated_postgres)
    engines = [app_engine(migrated_postgres) for _ in range(2)]
    ledgers = [PostgresBudgetLedger(engine) for engine in engines]
    try:
        scopes = [BudgetScope(session=f"lin-{n}", conversation=f"conv-{n}", day=DAY) for n in range(20)]
        results = await asyncio.gather(*(
            ledgers[n % 2].reserve(scope, tokens=10, cost=Decimal("0.01"), limits=LIMITS)
            for n, scope in enumerate(scopes)
        ))  # fmt: skip
        accepted = [result for result in results if result.refused_by is None]
        assert len(accepted) == 10
        assert {result.refused_by for result in results if result.refused_by is not None} == {BudgetCap.DAILY_COST}
        assert await ledgers[0].settle(scopes[0], tokens=0, cost=Decimal(0)) == Decimal("0.10")
    finally:
        for engine in engines:
            await engine.dispose()


async def test_an_unreachable_database_is_a_database_unavailable_error() -> None:
    engine = create_engine(
        database_url(user="bank_app", password=None, host="127.0.0.1", port=9, database="bank_agent"),
        pooled=False,
    )
    try:
        with pytest.raises(DatabaseUnavailableError):
            await PostgresBudgetLedger(engine).reserve(SCOPE, tokens=1, cost=Decimal(0), limits=LIMITS)
        with pytest.raises(DatabaseUnavailableError):
            await PostgresBudgetLedger(engine).settle(SCOPE, tokens=1, cost=Decimal(0))
    finally:
        await engine.dispose()
