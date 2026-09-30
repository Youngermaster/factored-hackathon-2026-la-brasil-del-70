"""Telemetry facade, so inner layers never import OpenTelemetry.

The OpenTelemetry adapter (``adapters/telemetry/opentelemetry.py``) implements it for the API; the no-op adapter serves
CLIs and the evaluation harness, and ``bank_agent.testing.telemetry`` records everything for assertions. Instrument
names, units, and attributes are listed in ``adapters/telemetry/catalog.py`` and ``docs/operations/observability.md``.
"""

from contextlib import AbstractContextManager
from typing import Protocol

AttributeValue = str | int | float | bool


class Span(Protocol):
    """An open span. Attribute values must never contain personal data or secrets."""

    @property
    def trace_id(self) -> str | None:
        """The 32-character hex trace id, or ``None`` when tracing is off."""
        ...

    @property
    def span_id(self) -> str | None:
        """The 16-character hex span id, or ``None`` when tracing is off."""
        ...

    def set_attribute(self, key: str, value: AttributeValue) -> None: ...

    def record_error_code(self, code: str) -> None:
        """Mark the span as failed with a domain error code (never an exception message)."""
        ...


class Counter(Protocol):
    def add(self, amount: float, attributes: dict[str, AttributeValue] | None = None) -> None: ...


class Histogram(Protocol):
    def record(self, value: float, attributes: dict[str, AttributeValue] | None = None) -> None: ...


class Gauge(Protocol):
    """The last value wins (a circuit state, a degradation level, a budget ratio)."""

    def set(self, value: float, attributes: dict[str, AttributeValue] | None = None) -> None: ...


class Telemetry(Protocol):
    """Spans and metrics.

    Preconditions: span and metric names are stable, lowercase, dot-separated identifiers.
    Postconditions: never raises for telemetry failures; a broken exporter must not break a turn.
    Errors: none; failures are swallowed and, at most, logged by the adapter.
    Isolation: callers pass identifiers and codes only, never message text or personal data.
    """

    def span(self, name: str, attributes: dict[str, AttributeValue] | None = None) -> AbstractContextManager[Span]:
        """Open a span for the duration of a ``with`` block."""
        ...

    def counter(self, name: str) -> Counter: ...

    def histogram(self, name: str) -> Histogram: ...

    def gauge(self, name: str) -> Gauge: ...

    def current_trace_id(self) -> str | None:
        """The 32-character hex trace id of the active span, or ``None`` outside a trace or with tracing off."""
        ...
