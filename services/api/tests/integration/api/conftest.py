"""API integration fixtures: the real container over PostgreSQL (testcontainers) or the in-memory adapters.

``api_backend`` is parameterized over both; ``postgres_api`` is PostgreSQL only. Tests build the app through
``backend.build(...)`` so each can inject a scripted ``FakeLLM`` or change settings first.
"""

from collections.abc import AsyncIterator

import pytest

from bank_agent.adapters.persistence.postgres.seed import PostgresSeeder, SeedBundle
from bank_agent_api import ApiBackend, api_environment, memory_persistence, postgres_identities
from bank_agent_postgres import owner_engine, reset_database
from bank_agent_scenarios import scenario_data
from bank_agent_test_support import PostgresInstance


async def _seed_postgres(instance: PostgresInstance) -> None:
    await reset_database(instance)
    data = scenario_data()
    identities, staff = postgres_identities()
    owner = owner_engine(instance)
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


def _point_at(instance: PostgresInstance, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", instance.host)
    monkeypatch.setenv("POSTGRES_PORT", str(instance.port))
    monkeypatch.setenv("POSTGRES_DB", instance.database)
    monkeypatch.setenv("POSTGRES_APP_USER", instance.app_user)
    monkeypatch.setenv("POSTGRES_APP_PASSWORD", instance.app_password)


async def _backend(name: str, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> ApiBackend:
    api_environment(monkeypatch)
    if name == "memory":
        return ApiBackend(name, memory_persistence)
    instance: PostgresInstance = request.getfixturevalue("migrated_postgres")
    await _seed_postgres(instance)
    _point_at(instance, monkeypatch)
    return ApiBackend(name, lambda: None)


@pytest.fixture(params=["memory", "postgres"])
async def api_backend(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[ApiBackend]:
    backend = await _backend(request.param, request, monkeypatch)
    yield backend
    for harness in backend.built:
        await harness.container.aclose()


@pytest.fixture
async def postgres_api(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[ApiBackend]:
    backend = await _backend("postgres", request, monkeypatch)
    yield backend
    for harness in backend.built:
        await harness.container.aclose()


@pytest.fixture
async def memory_api(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[ApiBackend]:
    """The in-memory adapters only, for tests that seed records the database would tie to other rows."""
    backend = await _backend("memory", request, monkeypatch)
    yield backend
    for harness in backend.built:
        await harness.container.aclose()
