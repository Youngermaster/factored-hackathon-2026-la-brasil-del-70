"""Backends for the workflow scenario tests: the in-memory adapters and PostgreSQL (testcontainers)."""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

import pytest

from bank_agent.adapters.persistence.memory.sessions import InMemorySessionStore
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory
from bank_agent.adapters.persistence.postgres.seed import PostgresSeeder, SeedBundle
from bank_agent.adapters.persistence.postgres.sessions import PostgresSessionStore
from bank_agent.adapters.persistence.postgres.unit_of_work import PostgresUnitOfWorkFactory
from bank_agent.ports.sessions import SessionStore
from bank_agent.ports.unit_of_work import UnitOfWorkFactory
from bank_agent_postgres import app_engine, owner_engine, reset_database
from bank_agent_scenarios import scenario_data
from bank_agent_test_support import PostgresInstance


@dataclass
class Backend:
    uow_factory: UnitOfWorkFactory
    session_store: SessionStore


async def memory_backend(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    data = scenario_data()
    store = InMemoryStore()
    store.seed(customers=data.customers, products=data.products, transactions=data.transactions, cases=data.cases)
    yield Backend(InMemoryUnitOfWorkFactory(store), InMemorySessionStore())


async def postgres_backend(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    instance: PostgresInstance = request.getfixturevalue("migrated_postgres")
    await reset_database(instance)
    data = scenario_data()
    owner = owner_engine(instance)
    try:
        bundle = SeedBundle(
            customers=data.customers, products=data.products, transactions=data.transactions, cases=data.cases
        )
        await PostgresSeeder(owner).load(bundle)
    finally:
        await owner.dispose()
    engine = app_engine(instance)
    try:
        yield Backend(PostgresUnitOfWorkFactory(engine), PostgresSessionStore(engine))
    finally:
        await engine.dispose()


BACKENDS: dict[str, Callable[[pytest.FixtureRequest], AsyncIterator[Backend]]] = {
    "memory": memory_backend,
    "postgres": postgres_backend,
}


@pytest.fixture(params=sorted(BACKENDS))
async def backend(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    async for value in BACKENDS[request.param](request):
        yield value


@pytest.fixture
async def postgres_only(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    async for value in postgres_backend(request):
        yield value
