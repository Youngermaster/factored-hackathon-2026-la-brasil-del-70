"""Fixtures for the shared contract suites: one seeded backend per parameter.

Tests here live outside ``tests/unit`` and ``tests/integration``, so each backend parameter carries its own
``unit`` or ``integration`` marker (see ``bank_agent_contracts``).
"""

from collections.abc import AsyncIterator, Callable

import pytest

from bank_agent_contracts import READ_BACKENDS, WRITE_BACKENDS, ReadBackend, WriteBackend, contract_dataset


@pytest.fixture(params=READ_BACKENDS)
async def read_backend(request: pytest.FixtureRequest) -> AsyncIterator[ReadBackend]:
    factory: Callable[[pytest.FixtureRequest], ReadBackend] = request.param
    backend = factory(request)
    await backend.seed(contract_dataset())
    yield backend
    await backend.aclose()


@pytest.fixture(params=WRITE_BACKENDS)
async def write_backend(request: pytest.FixtureRequest) -> AsyncIterator[WriteBackend]:
    factory: Callable[[pytest.FixtureRequest], WriteBackend] = request.param
    backend = factory(request)
    await backend.seed(contract_dataset())
    yield backend
    await backend.aclose()
