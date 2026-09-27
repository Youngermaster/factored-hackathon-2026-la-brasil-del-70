"""The in-process sliding-window rate limiter."""

import secrets

import pytest

from bank_agent.api.config import RateClass, RateLimit
from bank_agent.api.errors import RateLimitedError
from bank_agent.api.ratelimit import SlidingWindowLimiter

TOKEN = secrets.token_urlsafe(32)
OTHER = secrets.token_urlsafe(32)


class Ticks:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_refuses_after_the_limit_and_frees_slots_as_the_window_slides() -> None:
    ticks = Ticks()
    limiter = SlidingWindowLimiter(ticks)
    assert limiter.hit("k", 2) is None
    ticks.now += 10
    assert limiter.hit("k", 2) is None
    ticks.now += 5
    assert limiter.hit("k", 2) == pytest.approx(45.0)
    ticks.now += 45
    assert limiter.hit("k", 2) is None
    assert limiter.hit("other", 2) is None


def test_checks_the_ip_and_then_the_session_and_reports_whole_seconds_to_wait() -> None:
    ticks = Ticks()
    limiter = SlidingWindowLimiter(ticks)
    limit = RateLimit(per_ip=3, per_session=1)
    limiter.check(RateClass.WRITE, limit, client_ip="198.51.100.1", session_token=TOKEN)
    with pytest.raises(RateLimitedError) as refused:
        limiter.check(RateClass.WRITE, limit, client_ip="198.51.100.1", session_token=TOKEN)
    assert refused.value.retry_after_seconds == 60
    limiter.check(RateClass.WRITE, limit, client_ip="198.51.100.1", session_token=None)
    limiter.check(RateClass.READ, limit, client_ip="198.51.100.1", session_token=TOKEN)
    with pytest.raises(RateLimitedError):
        limiter.check(RateClass.WRITE, limit, client_ip="198.51.100.1", session_token=None)


def test_stale_keys_are_swept_once_the_table_grows() -> None:
    ticks = Ticks()
    limiter = SlidingWindowLimiter(ticks)
    for index in range(10_001):
        limiter.hit(f"key-{index}", 5)
    ticks.now += 61
    limiter.hit("fresh", 5)
    assert len(limiter._hits) == 1


def test_a_fraction_of_a_second_still_asks_to_wait_one_second() -> None:
    assert RateLimitedError(0.2).retry_after_seconds == 1
    assert RateLimitedError(1.01).retry_after_seconds == 2
