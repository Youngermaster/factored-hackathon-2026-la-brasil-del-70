"""The rate limiter over the in-process sliding log (the shared store's contract is in the integration suite)."""

import secrets

import pytest

from bank_agent.adapters.ratelimit.memory import InMemoryRateLimitStore
from bank_agent.api.config import RateClass, RateLimit
from bank_agent.api.errors import RateLimitedError
from bank_agent.api.ratelimit import RateLimiter

TOKEN = secrets.token_urlsafe(32)
OTHER = secrets.token_urlsafe(32)


class Ticks:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_refuses_after_the_limit_and_frees_slots_as_the_window_slides() -> None:
    ticks = Ticks()
    store = InMemoryRateLimitStore(ticks)
    assert await store.hit("k", 2) is None
    ticks.now += 10
    assert await store.hit("k", 2) is None
    ticks.now += 5
    assert await store.hit("k", 2) == pytest.approx(45.0)
    ticks.now += 45
    assert await store.hit("k", 2) is None
    assert await store.hit("other", 2) is None


async def test_checks_the_ip_and_then_the_session_and_reports_whole_seconds_to_wait() -> None:
    ticks = Ticks()
    limiter = RateLimiter(InMemoryRateLimitStore(ticks))
    limit = RateLimit(per_ip=3, per_session=1)
    await limiter.check(RateClass.WRITE, limit, client_ip="198.51.100.1", session_token=TOKEN)
    with pytest.raises(RateLimitedError) as refused:
        await limiter.check(RateClass.WRITE, limit, client_ip="198.51.100.1", session_token=TOKEN)
    assert refused.value.retry_after_seconds == 60
    await limiter.check(RateClass.WRITE, limit, client_ip="198.51.100.1", session_token=None)
    await limiter.check(RateClass.READ, limit, client_ip="198.51.100.1", session_token=TOKEN)
    with pytest.raises(RateLimitedError):
        await limiter.check(RateClass.WRITE, limit, client_ip="198.51.100.1", session_token=None)


async def test_the_session_key_is_a_digest_never_the_token() -> None:
    seen: list[str] = []

    class Recording:
        async def hit(self, key: str, limit: int) -> float | None:
            seen.append(key)
            return None

    limiter = RateLimiter(Recording())
    await limiter.check(RateClass.AUTH, RateLimit(1, 1), client_ip="192.0.2.1", session_token=OTHER)
    assert seen[0] == "auth:ip:192.0.2.1"
    assert seen[1].startswith("auth:session:")
    assert OTHER not in seen[1]
    assert limiter.store is not None


async def test_stale_keys_are_swept_once_the_table_grows() -> None:
    ticks = Ticks()
    store = InMemoryRateLimitStore(ticks)
    for index in range(10_001):
        await store.hit(f"key-{index}", 5)
    ticks.now += 61
    await store.hit("fresh", 5)
    assert len(store._hits) == 1


def test_a_fraction_of_a_second_still_asks_to_wait_one_second() -> None:
    assert RateLimitedError(0.2).retry_after_seconds == 1
    assert RateLimitedError(1.01).retry_after_seconds == 2
