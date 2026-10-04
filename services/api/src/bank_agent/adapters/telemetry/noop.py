"""A telemetry adapter that records nothing: CLIs, the evaluation harness, and tests that do not assert telemetry."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager

from bank_agent.ports.telemetry import AttributeValue


class NoopSpan:
    @property
    def trace_id(self) -> str | None:
        return None

    @property
    def span_id(self) -> str | None:
        return None

    def set_attribute(self, key: str, value: AttributeValue) -> None:
        """Discard the attribute."""

    def record_error_code(self, code: str) -> None:
        """Discard the error code."""


class NoopCounter:
    def add(self, amount: float, attributes: dict[str, AttributeValue] | None = None) -> None:
        """Discard the measurement."""


class NoopHistogram:
    def record(self, value: float, attributes: dict[str, AttributeValue] | None = None) -> None:
        """Discard the measurement."""


class NoopGauge:
    def set(self, value: float, attributes: dict[str, AttributeValue] | None = None) -> None:
        """Discard the measurement."""


class NoopTelemetry:
    """Implements the ``Telemetry`` port by discarding everything. It never raises."""

    def span(self, name: str, attributes: dict[str, AttributeValue] | None = None) -> AbstractContextManager[NoopSpan]:
        @contextmanager
        def _open() -> Iterator[NoopSpan]:
            yield NoopSpan()

        return _open()

    def counter(self, name: str) -> NoopCounter:
        return NoopCounter()

    def histogram(self, name: str) -> NoopHistogram:
        return NoopHistogram()

    def gauge(self, name: str) -> NoopGauge:
        return NoopGauge()

    def current_trace_id(self) -> str | None:
        return None
