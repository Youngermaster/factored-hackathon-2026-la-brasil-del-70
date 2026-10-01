"""A telemetry double that records spans and metrics for assertions."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field

from bank_agent.ports.telemetry import AttributeValue


@dataclass
class RecordedSpan:
    name: str
    attributes: dict[str, AttributeValue] = field(default_factory=dict)
    error_codes: list[str] = field(default_factory=list)
    trace_id: str | None = "0" * 31 + "1"
    span_id: str | None = "0" * 15 + "1"

    def set_attribute(self, key: str, value: AttributeValue) -> None:
        self.attributes[key] = value

    def record_error_code(self, code: str) -> None:
        self.error_codes.append(code)


@dataclass
class RecordedCounter:
    name: str
    total: float = 0
    points: list[tuple[float, dict[str, AttributeValue]]] = field(default_factory=list)

    def add(self, amount: float, attributes: dict[str, AttributeValue] | None = None) -> None:
        self.total += amount
        self.points.append((amount, dict(attributes or {})))


@dataclass
class RecordedHistogram:
    name: str
    values: list[tuple[float, dict[str, AttributeValue]]] = field(default_factory=list)

    def record(self, value: float, attributes: dict[str, AttributeValue] | None = None) -> None:
        self.values.append((value, dict(attributes or {})))


@dataclass
class RecordedGauge:
    name: str
    values: list[tuple[float, dict[str, AttributeValue]]] = field(default_factory=list)

    def set(self, value: float, attributes: dict[str, AttributeValue] | None = None) -> None:
        self.values.append((value, dict(attributes or {})))

    def last(self, **attributes: AttributeValue) -> float | None:
        """The newest value recorded with exactly these attributes."""
        matching = [value for value, recorded in self.values if recorded == attributes]
        return matching[-1] if matching else None


class RecordingTelemetry:
    """Implements the ``Telemetry`` port by keeping everything in memory."""

    def __init__(self) -> None:
        self.spans: list[RecordedSpan] = []
        self.counters: dict[str, RecordedCounter] = {}
        self.histograms: dict[str, RecordedHistogram] = {}
        self.gauges: dict[str, RecordedGauge] = {}

    def span(
        self, name: str, attributes: dict[str, AttributeValue] | None = None
    ) -> AbstractContextManager[RecordedSpan]:
        @contextmanager
        def _open() -> Iterator[RecordedSpan]:
            span = RecordedSpan(name=name, attributes=dict(attributes or {}))
            self.spans.append(span)
            yield span

        return _open()

    def counter(self, name: str) -> RecordedCounter:
        return self.counters.setdefault(name, RecordedCounter(name))

    def histogram(self, name: str) -> RecordedHistogram:
        return self.histograms.setdefault(name, RecordedHistogram(name))

    def gauge(self, name: str) -> RecordedGauge:
        return self.gauges.setdefault(name, RecordedGauge(name))

    def current_trace_id(self) -> str | None:
        return self.spans[-1].trace_id if self.spans else None
