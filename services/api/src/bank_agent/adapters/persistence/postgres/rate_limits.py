"""``PostgresRateLimitStore``: rate-limit counters in ``app.rate_limit_windows``, shared by every API process.

A sliding-window counter: one row per key digest and fixed window (60 seconds for the HTTP limits). A request at
``elapsed`` seconds into the current window is judged on ``current + floor(previous * (1 - elapsed / window))``, the
previous window's count weighted by how much of it still overlaps the sliding window. One transaction reads the previous
window and upserts the current one; the upsert's ``WHERE`` runs on the locked row, so concurrent workers never push a
window past its limit. A refused request is not counted, and the caller is told to wait until the current window ends.

Keys are stored as ``HMAC-SHA256(key, <class>:ip:<address>)`` digests with a key derived from ``SESSION_SECRET``, so the
table never holds an address or a session digest that could be matched without the server secret. Old windows are
deleted by the retention purge. Availability failures become ``DatabaseUnavailableError`` (the request fails closed).
"""

import hashlib
import hmac
import math
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bank_agent.adapters.persistence.postgres.database import is_unavailable, unavailable
from bank_agent.ports.determinism import Clock

DEFAULT_WINDOW_SECONDS: Final = 60
_KEY_LABEL: Final = b"bank-agent/rate-limit-key/v1"
_PREVIOUS: Final = "SELECT hits FROM app.rate_limit_windows WHERE key_digest = :key AND window_start = :start"
_COUNT: Final = (
    "INSERT INTO app.rate_limit_windows AS w (key_digest, window_start, hits) VALUES (:key, :start, 1) "
    "ON CONFLICT (key_digest, window_start) DO UPDATE SET hits = w.hits + 1 "
    "WHERE w.hits + :carried < :limit RETURNING w.hits"
)


def rate_limit_key(secret: bytes) -> bytes:
    """The HMAC key for stored digests, derived from the server secret with its own label."""
    return hmac.new(secret, _KEY_LABEL, hashlib.sha256).digest()


class PostgresRateLimitStore:
    """Implements ``RateLimitStore`` over the application-role engine."""

    def __init__(
        self, engine: AsyncEngine, clock: Clock, key: bytes, window_seconds: int = DEFAULT_WINDOW_SECONDS
    ) -> None:
        if len(key) < 32:
            raise ValueError("the rate-limit key needs at least 32 bytes")
        self._engine = engine
        self._clock = clock
        self._key = key
        self._window = window_seconds

    def __repr__(self) -> str:
        return f"PostgresRateLimitStore(window_seconds={self._window})"

    def digest(self, key: str) -> str:
        return hmac.new(self._key, key.encode("utf-8"), hashlib.sha256).hexdigest()

    async def hit(self, key: str, limit: int) -> float | None:
        now = self._clock.now().timestamp()
        start = math.floor(now / self._window) * self._window
        elapsed = now - start
        wait = max(self._window - elapsed, 0.001)
        current = datetime.fromtimestamp(start, UTC)
        digest = self.digest(key)
        try:
            async with self._engine.begin() as connection:
                previous = await connection.execute(
                    text(_PREVIOUS), {"key": digest, "start": current - timedelta(seconds=self._window)}
                )
                carried = math.floor((previous.scalar() or 0) * (1 - elapsed / self._window))
                if carried >= limit:
                    return wait
                counted = await connection.execute(
                    text(_COUNT), {"key": digest, "start": current, "carried": carried, "limit": limit}
                )
                return None if counted.first() is not None else wait
        except Exception as error:
            if is_unavailable(error):
                raise unavailable(error) from error
            raise
