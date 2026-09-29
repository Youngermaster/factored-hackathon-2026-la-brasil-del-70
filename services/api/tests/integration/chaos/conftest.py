"""Chaos suite fixtures: the workflow backends (memory and PostgreSQL), the API over each, and the owner engine."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from bank_agent.adapters.persistence.postgres.seed import PostgresSeeder, SeedBundle
from bank_agent_api import ApiBackend, api_environment, memory_persistence, postgres_identities
from bank_agent_postgres import owner_engine, reset_database
from bank_agent_scenarios import scenario_data
from bank_agent_test_support import PostgresInstance
from bank_agent_workflow_support import BACKENDS, Backend, postgres_backend


@pytest.fixture(params=sorted(BACKENDS))
async def backend(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    async for value in BACKENDS[request.param](request):
        yield value


@pytest.fixture
async def postgres_only(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    async for value in postgres_backend(request):
        yield value


@pytest.fixture
async def owner(migrated_postgres: PostgresInstance) -> AsyncIterator[AsyncEngine]:
    engine = owner_engine(migrated_postgres)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def memory_api(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[ApiBackend]:
    api_environment(monkeypatch)
    backend = ApiBackend("memory", memory_persistence)
    yield backend
    for harness in backend.built:
        await harness.container.aclose()


@pytest.fixture
async def postgres_api(
    migrated_postgres: PostgresInstance, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[ApiBackend]:
    """The API over the seeded PostgreSQL container, connecting as the application role."""
    api_environment(monkeypatch)
    await reset_database(migrated_postgres)
    data = scenario_data()
    identities, staff = postgres_identities()
    owner = owner_engine(migrated_postgres)
    try:
        bundle = SeedBundle(
            customers=data.customers,
            products=data.products,
            transactions=data.transactions,
            cases=data.cases,
            credit_profiles=data.credit_profiles,
            identities=identities,
            staff=staff,
        )
        await PostgresSeeder(owner).load(bundle)
    finally:
        await owner.dispose()
    for name, value in (
        ("POSTGRES_HOST", migrated_postgres.host),
        ("POSTGRES_PORT", str(migrated_postgres.port)),
        ("POSTGRES_DB", migrated_postgres.database),
        ("POSTGRES_APP_USER", migrated_postgres.app_user),
        ("POSTGRES_APP_PASSWORD", migrated_postgres.app_password),
    ):
        monkeypatch.setenv(name, value)
    backend = ApiBackend("postgres", lambda: None)
    yield backend
    for harness in backend.built:
        await harness.container.aclose()
