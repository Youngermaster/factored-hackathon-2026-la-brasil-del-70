"""Backends for the workflow scenario tests: the in-memory adapters and PostgreSQL (testcontainers)."""

from collections.abc import AsyncIterator

import pytest

from bank_agent_workflow_support import BACKENDS, Backend, postgres_backend


@pytest.fixture(params=sorted(BACKENDS))
async def backend(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    async for value in BACKENDS[request.param](request):
        yield value


@pytest.fixture
async def postgres_only(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    async for value in postgres_backend(request):
        yield value
