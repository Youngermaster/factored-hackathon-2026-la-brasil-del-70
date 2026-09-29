from collections.abc import Sequence

import httpx

from bank_agent.api.app import create_app
from bank_agent.application.reliability.ladder import LadderFlags, Signals, StaticDegradation, assess
from bank_agent.domain.degradation import ComponentState
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


def _details_client(provider: FakeProvider) -> httpx.AsyncClient:
    app = create_app(provider, api_config())
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def test_details_report_the_level_reasons_and_components() -> None:
    status = assess(Signals(llm_primary=ComponentState.UNAVAILABLE, database=ComponentState.OK), LadderFlags())
    provider = FakeProvider([StaticReadinessCheck("database", healthy=True)], StaticDegradation(status))
    async with _details_client(provider) as client:
        response = await client.get("/health/details")

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["level"], body["reasons"], body["template_only"]) == (
        "degraded",
        "L2",
        ["llm_unavailable"],
        True,
    )
    assert body["components"]["llm_primary"] == "unavailable"
    assert body["checks"] == {"database": "ok"}
    assert provider.degradation.database_probes == [True]


async def test_details_answer_503_at_l4_and_readiness_feeds_the_database_probe() -> None:
    status = assess(Signals(database=ComponentState.UNAVAILABLE), LadderFlags())
    provider = FakeProvider([StaticReadinessCheck("database", healthy=False)], StaticDegradation(status))
    async with _details_client(provider) as client:
        details = await client.get("/health/details")
        ready = await client.get("/health/ready")

    assert (details.status_code, details.json()["status"], details.json()["level"]) == (503, "unavailable", "L4")
    assert ready.status_code == 503
    assert provider.degradation.database_probes == [False, False]


async def test_details_are_normal_without_degradation() -> None:
    async with _details_client(FakeProvider()) as client:
        response = await client.get("/health/details")

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["level"]) == ("normal", "L0")
