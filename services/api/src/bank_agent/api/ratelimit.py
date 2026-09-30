"""Rate limits per client IP and per session over a ``RateLimitStore`` (ADR 0031).

Keys are ``<class>:ip:<address>`` and ``<class>:session:<digest>`` (never the raw session token). The store decides
where the counters live: in this process (``InMemoryRateLimitStore``, development and tests) or in PostgreSQL, shared
by every worker (``PostgresRateLimitStore``, required in production). The client address is the ASGI client, which
uvicorn sets from ``X-Forwarded-For`` only when the peer is the trusted reverse proxy (``--forwarded-allow-ips``).
"""

import hashlib

from bank_agent.api.config import RateClass, RateLimit
from bank_agent.api.errors import RateLimitedError
from bank_agent.ports.rate_limits import RateLimitStore


class RateLimiter:
    def __init__(self, store: RateLimitStore) -> None:
        self._store = store

    @property
    def store(self) -> RateLimitStore:
        return self._store

    async def check(
        self, rate_class: RateClass, limit: RateLimit, *, client_ip: str, session_token: str | None
    ) -> None:
        """Raise ``RateLimitedError`` when the IP or the session is over its limit for ``rate_class``."""
        wait = await self._store.hit(f"{rate_class.value}:ip:{client_ip}", limit.per_ip)
        if wait is not None:
            raise RateLimitedError(wait, key="ip")
        if session_token:
            digest = hashlib.sha256(session_token.encode("utf-8")).hexdigest()[:32]
            wait = await self._store.hit(f"{rate_class.value}:session:{digest}", limit.per_session)
            if wait is not None:
                raise RateLimitedError(wait, key="session")
