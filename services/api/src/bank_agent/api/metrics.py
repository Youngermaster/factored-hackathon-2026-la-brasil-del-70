"""HTTP-layer metrics: rate-limit rejections and the sessions this process is serving.

HTTP latency histograms come from the OpenTelemetry FastAPI instrumentation (``http.server.request.duration``); this
module adds what only the HTTP layer knows. Active sessions are the sessions that made a request within their idle
timeout, counted per process (the dashboard sums the processes); the gauge holds opaque session ids only in memory
and never exports them.
"""

from datetime import datetime

from bank_agent.api.config import RateClass
from bank_agent.domain.session import Session
from bank_agent.ports.telemetry import Telemetry


class HttpMetrics:
    def __init__(self, telemetry: Telemetry) -> None:
        self._rate_limited = telemetry.counter("bank.http.rate_limited")
        self._active = telemetry.gauge("bank.sessions.active")
        self._expiry: dict[str, datetime] = {}

    def rate_limited(self, rate_class: RateClass, key: str) -> None:
        """Count one refusal; ``key`` is ``ip`` or ``session``, never the address or the token."""
        self._rate_limited.add(1, {"bank.rate_class": rate_class.value, "bank.rate_key": key})

    def session_seen(self, session: Session, now: datetime) -> None:
        """Remember that ``session`` was active at ``now`` until its idle timeout, and publish the count."""
        self._expiry[session.session_id] = now + session.idle_timeout
        for session_id in [key for key, expires in self._expiry.items() if expires <= now]:
            del self._expiry[session_id]
        self._active.set(len(self._expiry))

    @property
    def active_sessions(self) -> int:
        return len(self._expiry)
