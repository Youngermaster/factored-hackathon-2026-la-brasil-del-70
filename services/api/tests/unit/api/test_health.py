from collections.abc import Sequence

import httpx

from bank_agent.api.app import create_app
from bank_agent.ports.health import ReadinessCheck
from bank_agent_test_support import (
    FakeProvider,
    HangingReadinessCheck,
    RaisingReadinessCheck,
    StaticReadinessCheck,
    api_config,
)


def _client(checks: Sequence[ReadinessCheck] = (), timeout_seconds: float = 2.0) -> httpx.AsyncClient:
    app = create_app(FakeProvider(checks), api_config(timeout_seconds=timeout_seconds))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def test_live_always_reports_live() -> None:
    async with _client([StaticReadinessCheck("database", healthy=False)]) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


async def test_ready_without_configured_dependencies_reports_ready() -> None:
    async with _client() as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {}}


async def test_ready_reports_each_healthy_dependency() -> None:
    checks = [StaticReadinessCheck("database", healthy=True), StaticReadinessCheck("cache", healthy=True)]
    async with _client(checks) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok", "cache": "ok"}}


async def test_ready_returns_503_when_a_dependency_is_unavailable() -> None:
    checks = [StaticReadinessCheck("database", healthy=False), StaticReadinessCheck("cache", healthy=True)]
    async with _client(checks) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"database": "unavailable", "cache": "ok"}}


async def test_ready_hides_the_error_text_of_a_failing_check() -> None:
    async with _client([RaisingReadinessCheck("database", "password authentication failed for bank_app")]) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"database": "unavailable"}}
    assert "password" not in response.text


async def test_ready_treats_a_check_that_times_out_as_unavailable() -> None:
    async with _client([HangingReadinessCheck()], timeout_seconds=0.05) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"slow": "unavailable"}}


async def test_shutdown_closes_the_provider() -> None:
    provider = FakeProvider()
    app = create_app(provider, api_config())

    async with app.router.lifespan_context(app):
        assert provider.closed is False

    assert provider.closed is True


def test_docs_can_be_hidden() -> None:
    app = create_app(FakeProvider(), api_config(expose_docs=False))

    assert app.docs_url is None
    assert app.openapi_url is None
