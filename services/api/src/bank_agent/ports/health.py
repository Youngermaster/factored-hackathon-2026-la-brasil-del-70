"""Readiness port: a dependency the service needs before it can accept traffic."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ReadinessCheck(Protocol):
    """Checks one dependency, such as the database, for readiness.

    Implementations must not raise for an unavailable dependency; they return ``False``. They must never
    include connection details or credentials in anything they log or return.
    """

    @property
    def name(self) -> str:
        """Stable, lowercase identifier reported by ``/health/ready`` (for example ``database``)."""
        ...

    async def check(self) -> bool:
        """Return ``True`` when the dependency is reachable and usable."""
        ...
