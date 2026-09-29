"""Degradation port: where the engine and the health probes learn the current degradation level."""

from typing import Protocol

from bank_agent.domain.degradation import DegradationStatus


class DegradationSource(Protocol):
    """The current rung of the degradation ladder (``bank_agent.domain.degradation``).

    Preconditions: none; it may be called at any time, concurrently with traffic, once per turn and per probe.
    Postconditions: ``current`` returns the level and the active reasons from the latest known dependency state
    (circuit breakers, the budget ledger, startup load results, the last database probe) without blocking on I/O.
    Errors: none; an implementation that cannot determine a component reports it ``unavailable``, never ``ok``.
    Isolation: the status carries component names and reason codes only, never connection details or messages.
    """

    def current(self) -> DegradationStatus:
        """The status now; also publishes the level and component gauges when the implementation has telemetry."""
        ...

    def record_database(self, available: bool) -> None:
        """The outcome of the latest database probe or a connection failure seen by a request."""
        ...
