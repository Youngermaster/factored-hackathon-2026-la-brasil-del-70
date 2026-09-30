"""``InMemoryRateLimitStore``: an exact sliding log of accepted request instants per key, in one process.

Each key keeps the instants of its accepted requests in the last window; a request is refused when the window is full,
with the seconds until the oldest instant leaves it. Several workers each keep their own counters, so production uses
the shared PostgreSQL store (``RATE_LIMIT_BACKEND=postgres``).
"""

from collections import deque
from collections.abc import Callable
from typing import Final

DEFAULT_WINDOW_SECONDS: Final = 60.0
_SWEEP_THRESHOLD: Final = 10_000


class InMemoryRateLimitStore:
    """Implements ``RateLimitStore`` over a monotonic clock."""

    def __init__(self, monotonic: Callable[[], float], window_seconds: float = DEFAULT_WINDOW_SECONDS) -> None:
        self._monotonic = monotonic
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def _sweep(self, now: float) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or now - hits[-1] >= self._window]
        for key in stale:
            del self._hits[key]

    async def hit(self, key: str, limit: int) -> float | None:
        now = self._monotonic()
        if len(self._hits) > _SWEEP_THRESHOLD:
            self._sweep(now)
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self._window:
            hits.popleft()
        if len(hits) >= limit:
            return self._window - (now - hits[0])
        hits.append(now)
        return None
