"""In-process sliding-window rate limits per client IP and per session (ADR 0031).

Each key keeps the instants of its accepted requests in the last window; a request is refused when the window is
full, with the seconds until the oldest instant leaves it. Keys are ``<class>:ip:<address>`` and
``<class>:session:<digest>`` (never the raw session token). Counters live in one process: several workers each
enforce their own limits (BACKLOG, phase 16).
"""

import hashlib
from collections import deque
from collections.abc import Callable
from typing import Final

from bank_agent.api.config import RateClass, RateLimit
from bank_agent.api.errors import RateLimitedError

WINDOW_SECONDS: Final = 60.0
_SWEEP_THRESHOLD: Final = 10_000


class SlidingWindowLimiter:
    def __init__(self, monotonic: Callable[[], float], window_seconds: float = WINDOW_SECONDS) -> None:
        self._monotonic = monotonic
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def _sweep(self, now: float) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or now - hits[-1] >= self._window]
        for key in stale:
            del self._hits[key]

    def hit(self, key: str, limit: int) -> float | None:
        """Count a request for ``key``. Return ``None`` when accepted, or the seconds to wait when refused."""
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

    def check(self, rate_class: RateClass, limit: RateLimit, *, client_ip: str, session_token: str | None) -> None:
        """Raise ``RateLimitedError`` when the IP or the session is over its limit for ``rate_class``."""
        wait = self.hit(f"{rate_class.value}:ip:{client_ip}", limit.per_ip)
        if wait is not None:
            raise RateLimitedError(wait, key="ip")
        if session_token:
            digest = hashlib.sha256(session_token.encode("utf-8")).hexdigest()[:32]
            wait = self.hit(f"{rate_class.value}:session:{digest}", limit.per_session)
            if wait is not None:
                raise RateLimitedError(wait, key="session")
