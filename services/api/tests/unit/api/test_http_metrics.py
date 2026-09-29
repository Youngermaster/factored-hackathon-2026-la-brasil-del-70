"""HTTP metrics: rate-limit rejections by class and key kind, and the active sessions of this process."""

from datetime import timedelta

import httpx
import pytest

from bank_agent.api.app import create_app
from bank_agent.api.config import RateClass, RateLimit, SecurityConfig
from bank_agent.api.errors import RateLimitedError
from bank_agent.api.metrics import HttpMetrics
from bank_agent.api.ratelimit import SlidingWindowLimiter
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_builders import T0, session
from bank_agent_test_support import FakeProvider, api_config

TOKEN_A, TOKEN_B = "fixture-session-a", "fixture-session-b"  # nosec B105 (fixture tokens)


def test_active_sessions_expire_after_their_idle_timeout() -> None:
    telemetry = RecordingTelemetry()
    metrics = HttpMetrics(telemetry)
    first = session(session_id="ses-first")
    second = session(session_id="ses-second")
    metrics.session_seen(first, T0)
    metrics.session_seen(second, T0 + timedelta(minutes=10))
    assert metrics.active_sessions == 2
    metrics.session_seen(second, T0 + first.idle_timeout + timedelta(seconds=1))
    assert metrics.active_sessions == 1
    assert telemetry.gauges["bank.sessions.active"].last() == 1


def test_the_limiter_names_which_limit_refused() -> None:
    limiter = SlidingWindowLimiter(lambda: 0.0)
    limit = RateLimit(per_ip=1, per_session=1)
    limiter.check(RateClass.READ, limit, client_ip="198.51.100.1", session_token=TOKEN_A)
    with pytest.raises(RateLimitedError) as by_ip:
        limiter.check(RateClass.READ, limit, client_ip="198.51.100.1", session_token=TOKEN_B)
    assert by_ip.value.key == "ip"
    with pytest.raises(RateLimitedError) as by_session:
        limiter.check(RateClass.READ, limit, client_ip="198.51.100.2", session_token=TOKEN_A)
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
