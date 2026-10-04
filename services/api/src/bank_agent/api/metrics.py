"""HTTP-layer metrics: rate-limit rejections and the live sessions of the whole deployment.

HTTP latency histograms come from the OpenTelemetry FastAPI instrumentation (``http.server.request.duration``); this
module adds what only the HTTP layer knows. Active sessions are counted in the shared session store every
``ACTIVE_SESSIONS_INTERVAL_SECONDS`` by each API process, so every process reports the same deployment-wide number
(the dashboard takes the maximum, not the sum); the gauge carries a count only, never an id.
"""

import asyncio
from typing import Final

import structlog

from bank_agent.api.config import RateClass
from bank_agent.application.identity.sessions import SessionService
from bank_agent.ports.telemetry import Telemetry

ACTIVE_SESSIONS_INTERVAL_SECONDS: Final = 30.0
_log = structlog.get_logger(__name__)


class HttpMetrics:
    def __init__(self, telemetry: Telemetry) -> None:
        self._rate_limited = telemetry.counter("bank.http.rate_limited")
        self._active = telemetry.gauge("bank.sessions.active")
        self._active_count: int | None = None

    def rate_limited(self, rate_class: RateClass, key: str) -> None:
        """Count one refusal; ``key`` is ``ip`` or ``session``, never the address or the token."""
        self._rate_limited.add(1, {"bank.rate_class": rate_class.value, "bank.rate_key": key})

    async def refresh_active_sessions(self, sessions: SessionService | None) -> int | None:
        """Count the live sessions in the shared store and publish the gauge; ``None`` when it could not count."""
        if sessions is None:
            return None
        try:
            count = await sessions.count_active()
        except Exception as error:  # a database outage must not stop the loop; readiness reports it
            _log.warning("active_sessions_unavailable", error_type=type(error).__name__)
            return None
        self._active_count = count
        self._active.set(count)
        return count

    async def publish_active_sessions(
        self, sessions: SessionService | None, interval_seconds: float = ACTIVE_SESSIONS_INTERVAL_SECONDS
    ) -> None:
        """Refresh the gauge forever, every ``interval_seconds`` (a background task of the application lifespan)."""
        while True:
            await self.refresh_active_sessions(sessions)
            await asyncio.sleep(interval_seconds)

    @property
    def active_sessions(self) -> int | None:
        return self._active_count
