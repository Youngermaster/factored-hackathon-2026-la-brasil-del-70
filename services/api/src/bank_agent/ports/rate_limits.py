"""Rate-limit store port: request counters per key over a fixed window, in one process or shared by all of them."""

from typing import Protocol


class RateLimitStore(Protocol):
    """Counts requests per opaque key (``<class>:ip:<address>`` or ``<class>:session:<digest>``).

    Preconditions: ``limit`` is at least 1. The window length is fixed when the store is built (60 seconds for the HTTP
    limits).
    Postconditions: ``hit`` counts an accepted request and returns ``None``; a refused request is not counted and the
    return value is the number of seconds (greater than zero) after which a new request may be accepted. Stores may
    approximate the window (the shared store weights the previous window), but never accept more than ``limit``
    requests in any one window of their own.
    Errors: a shared store raises ``DatabaseUnavailableError`` when it cannot reach its database; the caller fails
    closed.
    Isolation: keys are opaque; a store that persists them stores a keyed digest, never the raw address or token.
    """

    async def hit(self, key: str, limit: int) -> float | None:
        """Count one request for ``key`` against ``limit``; ``None`` when accepted, else the seconds to wait."""
        ...
