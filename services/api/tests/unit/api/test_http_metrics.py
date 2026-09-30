"""HTTP metrics: rate-limit rejections by class and key kind, and the deployment-wide active sessions."""

import asyncio
import contextlib

import httpx
import pytest

from bank_agent.adapters.ratelimit.memory import InMemoryRateLimitStore
from bank_agent.api.app import create_app
from bank_agent.api.config import RateClass, RateLimit, SecurityConfig
from bank_agent.api.errors import RateLimitedError
from bank_agent.api.metrics import HttpMetrics
from bank_agent.api.ratelimit import RateLimiter
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_test_support import FakeProvider, api_config

TOKEN_A, TOKEN_B = "fixture-session-a", "fixture-session-b"  # nosec B105 (fixture tokens)


class _Sessions:
    def __init__(self, counts: list[int | Exception]) -> None:
        self._counts = counts

    async def count_active(self) -> int:
        value = self._counts.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


async def test_the_active_session_gauge_is_the_shared_count_and_survives_an_outage() -> None:
    telemetry = RecordingTelemetry()
    metrics = HttpMetrics(telemetry)
    sessions = _Sessions([3, ConnectionError("database down"), 1])
    assert await metrics.refresh_active_sessions(None) is None
    assert await metrics.refresh_active_sessions(sessions) == 3  # type: ignore[arg-type]
    assert await metrics.refresh_active_sessions(sessions) is None  # type: ignore[arg-type]
    assert metrics.active_sessions == 3
    assert await metrics.refresh_active_sessions(sessions) == 1  # type: ignore[arg-type]
    assert telemetry.gauges["bank.sessions.active"].last() == 1


async def test_the_publisher_refreshes_until_it_is_cancelled() -> None:
    metrics = HttpMetrics(RecordingTelemetry())
    task = asyncio.create_task(metrics.publish_active_sessions(_Sessions([2, 2, 2]), interval_seconds=0.001))  # type: ignore[arg-type]
    for _ in range(50):
        await asyncio.sleep(0.001)
        if metrics.active_sessions == 2:
            break
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert metrics.active_sessions == 2


async def test_the_limiter_names_which_limit_refused() -> None:
    limiter = RateLimiter(InMemoryRateLimitStore(lambda: 0.0))
    limit = RateLimit(per_ip=1, per_session=1)
    await limiter.check(RateClass.READ, limit, client_ip="198.51.100.1", session_token=TOKEN_A)
    with pytest.raises(RateLimitedError) as by_ip:
        await limiter.check(RateClass.READ, limit, client_ip="198.51.100.1", session_token=TOKEN_B)
    assert by_ip.value.key == "ip"
    with pytest.raises(RateLimitedError) as by_session:
        await limiter.check(RateClass.READ, limit, client_ip="198.51.100.2", session_token=TOKEN_A)
    assert by_session.value.key == "session"


async def test_a_rate_limited_request_is_counted_by_class_and_key() -> None:
    provider = FakeProvider()
    limits = {rate_class: RateLimit(per_ip=1, per_session=1) for rate_class in RateClass}
    config = api_config(security=SecurityConfig.development(rate_limits=limits))
    app = create_app(provider, config)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        await client.get("/v1/auth/csrf")
        refused = await client.get("/v1/auth/csrf")
    assert refused.status_code == 429
    assert provider.telemetry.counters["bank.http.rate_limited"].points == [
        (1, {"bank.rate_class": "auth", "bank.rate_key": "ip"})
    ]
