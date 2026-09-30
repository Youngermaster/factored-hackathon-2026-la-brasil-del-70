"""The rate-limit store contract on memory and PostgreSQL, and the shared store across workers."""

import asyncio
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from bank_agent.adapters.persistence.postgres.database import create_engine, database_url
from bank_agent.adapters.persistence.postgres.rate_limits import PostgresRateLimitStore, rate_limit_key
from bank_agent.adapters.ratelimit.memory import InMemoryRateLimitStore
from bank_agent.domain.errors import DatabaseUnavailableError
from bank_agent.ports.rate_limits import RateLimitStore
from bank_agent_postgres import app_engine, owner_engine, reset_database
from bank_agent_test_support import PostgresInstance

WINDOW_START = 1_790_000_040.0
"""A window boundary (a multiple of 60 seconds since the epoch), so the tests know where each window starts."""
KEY = rate_limit_key(secrets.token_bytes(32))


class Ticks:
    """One controllable instant, read as a monotonic float (memory store) and as a UTC clock (shared store)."""

    def __init__(self) -> None:
        self.at = WINDOW_START

    def __call__(self) -> float:
        return self.at

    def now(self) -> datetime:
        return datetime.fromtimestamp(self.at, UTC)


@pytest.fixture
def ticks() -> Ticks:
    return Ticks()


@pytest.fixture(params=["memory", "postgres"])
async def store(request: pytest.FixtureRequest, ticks: Ticks) -> AsyncIterator[RateLimitStore]:
    if request.param == "memory":
        yield InMemoryRateLimitStore(ticks)
        return
    instance: PostgresInstance = request.getfixturevalue("migrated_postgres")
    await reset_database(instance)
    engine = app_engine(instance)
    try:
        yield PostgresRateLimitStore(engine, ticks, KEY)
    finally:
        await engine.dispose()


async def test_accepts_up_to_the_limit_then_refuses_with_a_wait_inside_the_window(
    store: RateLimitStore, ticks: Ticks
) -> None:
    ticks.at += 15
    assert [await store.hit("auth:ip:198.51.100.7", 3) for _ in range(3)] == [None, None, None]
    wait = await store.hit("auth:ip:198.51.100.7", 3)
    assert wait is not None
    assert 0 < wait <= 60
    assert await store.hit("auth:ip:198.51.100.8", 3) is None


async def test_a_quiet_key_is_accepted_again_once_its_windows_pass(store: RateLimitStore, ticks: Ticks) -> None:
    for _ in range(2):
        assert await store.hit("write:session:abc", 2) is None
    assert await store.hit("write:session:abc", 2) is not None
    ticks.at += 120
    assert await store.hit("write:session:abc", 2) is None


async def test_the_shared_store_carries_the_overlapping_part_of_the_previous_window(
    migrated_postgres: PostgresInstance, ticks: Ticks
) -> None:
    await reset_database(migrated_postgres)
    engine = app_engine(migrated_postgres)
    store = PostgresRateLimitStore(engine, ticks, KEY)
    try:
        for _ in range(4):
            assert await store.hit("read:ip:203.0.113.4", 4) is None
        ticks.at += 90  # half way into the next window: floor(4 * 0.5) = 2 still count
        assert [await store.hit("read:ip:203.0.113.4", 4) for _ in range(3)] == [None, None, 30.0]
    finally:
        await engine.dispose()


async def test_workers_share_one_limit_and_never_exceed_it(migrated_postgres: PostgresInstance, ticks: Ticks) -> None:
    await reset_database(migrated_postgres)
    engines = [app_engine(migrated_postgres) for _ in range(2)]
    stores = [PostgresRateLimitStore(engine, ticks, KEY) for engine in engines]
    try:
        results = await asyncio.gather(*(stores[n % 2].hit("auth:ip:192.0.2.10", 10) for n in range(25)))
    finally:
        for engine in engines:
            await engine.dispose()
    assert sum(result is None for result in results) == 10


async def test_the_table_holds_keyed_digests_never_the_address(
    migrated_postgres: PostgresInstance, ticks: Ticks
) -> None:
    await reset_database(migrated_postgres)
    engine = app_engine(migrated_postgres)
    store = PostgresRateLimitStore(engine, ticks, KEY)
    owner = owner_engine(migrated_postgres)
    try:
        await store.hit("auth:ip:192.0.2.55", 5)
        async with owner.connect() as connection:
            result = await connection.execute(text("SELECT key_digest FROM app.rate_limit_windows"))
            stored = [str(row.key_digest) for row in result]
    finally:
        await engine.dispose()
        await owner.dispose()
    assert stored == [store.digest("auth:ip:192.0.2.55")]
    assert "192.0.2.55" not in repr(stored)


async def test_the_application_role_cannot_delete_windows(migrated_postgres: PostgresInstance, ticks: Ticks) -> None:
    await reset_database(migrated_postgres)
    engine = app_engine(migrated_postgres)
    try:
        await PostgresRateLimitStore(engine, ticks, KEY).hit("auth:ip:192.0.2.1", 5)
        async with engine.begin() as connection:
            with pytest.raises(Exception, match="permission denied"):
                await connection.execute(text("DELETE FROM app.rate_limit_windows"))
    finally:
        await engine.dispose()


async def test_an_unreachable_database_fails_closed(ticks: Ticks) -> None:
    url = database_url(user="bank_app", password=None, host="127.0.0.1", port=1, database="bank_agent")
    engine = create_engine(url, pooled=False)
    try:
        with pytest.raises(DatabaseUnavailableError):
            await PostgresRateLimitStore(engine, ticks, KEY).hit("auth:ip:192.0.2.1", 5)
    finally:
        await engine.dispose()


def test_the_shared_store_refuses_a_short_key(ticks: Ticks) -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        PostgresRateLimitStore(create_engine(database_url(user="u", password=None, host="h", port=1, database="d")),
                               ticks, b"short")  # fmt: skip
