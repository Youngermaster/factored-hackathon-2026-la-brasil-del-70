"""The ``Telemetry`` port over the OpenTelemetry API.

Spans come from a tracer and metrics from a meter, both created with the schema URL of the GenAI semantic conventions
this service writes (``GENAI_SEMCONV_VERSION``, 1.37.0). Units, descriptions, and histogram buckets come from the
instrument catalog, so callers pass only a name. The adapter never raises for a telemetry failure: a broken tracer or
meter degrades to a no-op for that call and logs the error type once per instrument. Exceptions raised by the code
inside a span still propagate; the span records only the exception's type name, never its message.
"""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Final

import structlog
from opentelemetry import trace
from opentelemetry.metrics import Meter, MeterProvider
from opentelemetry.trace import Span as OtelSpan
from opentelemetry.trace import Status, StatusCode, Tracer, TracerProvider

from bank_agent import __version__
from bank_agent.adapters.llm.tracing import GENAI_SEMCONV_VERSION
from bank_agent.adapters.telemetry.catalog import CATALOG, Kind
from bank_agent.adapters.telemetry.noop import NoopCounter, NoopGauge, NoopHistogram, NoopSpan
from bank_agent.ports.telemetry import AttributeValue, Counter, Gauge, Histogram, Span

SCHEMA_URL: Final = f"https://opentelemetry.io/schemas/{GENAI_SEMCONV_VERSION}"
INSTRUMENTATION_NAME: Final = "bank_agent"
_log = structlog.get_logger(__name__)


def trace_id_of(span: OtelSpan) -> str | None:
    context = span.get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None


class OtelSpanHandle:
    """Implements the port's ``Span`` over an OpenTelemetry span."""

    def __init__(self, span: OtelSpan) -> None:
        self._span = span

    @property
    def trace_id(self) -> str | None:
        return trace_id_of(self._span)

    @property
    def span_id(self) -> str | None:
        context = self._span.get_span_context()
        return format(context.span_id, "016x") if context.is_valid else None

    def set_attribute(self, key: str, value: AttributeValue) -> None:
        try:
            self._span.set_attribute(key, value)
        except Exception as error:  # telemetry must never break a turn
            _log.debug("telemetry_attribute_failed", error_type=type(error).__name__)

    def record_error_code(self, code: str) -> None:
        try:
            self._span.set_attribute("error.type", code)
            self._span.set_status(Status(StatusCode.ERROR, code))
        except Exception as error:  # telemetry must never break a turn
            _log.debug("telemetry_status_failed", error_type=type(error).__name__)


class _Instrument:
    """A counter, histogram, or gauge that swallows its own failures."""

    def __init__(self, name: str, record: Callable[..., None]) -> None:
        self._name = name
        self._record = record
        self._warned = False

    def _call(self, value: float, attributes: dict[str, AttributeValue] | None) -> None:
        try:
            self._record(value, attributes or {})
        except Exception as error:  # telemetry must never break a turn
            if not self._warned:
                self._warned = True
                _log.warning("telemetry_metric_failed", metric=self._name, error_type=type(error).__name__)

    def add(self, amount: float, attributes: dict[str, AttributeValue] | None = None) -> None:
        self._call(amount, attributes)

    def record(self, value: float, attributes: dict[str, AttributeValue] | None = None) -> None:
        self._call(value, attributes)

    def set(self, value: float, attributes: dict[str, AttributeValue] | None = None) -> None:
        self._call(value, attributes)


class OpenTelemetryAdapter:
    """Implements ``Telemetry``. The providers are passed in, so tests use in-memory exporters and no globals."""

    def __init__(self, tracer_provider: TracerProvider, meter_provider: MeterProvider) -> None:
        self._tracer: Tracer = tracer_provider.get_tracer(INSTRUMENTATION_NAME, __version__, schema_url=SCHEMA_URL)
        self._meter: Meter = meter_provider.get_meter(INSTRUMENTATION_NAME, __version__, schema_url=SCHEMA_URL)
        self._instruments: dict[str, _Instrument] = {}

    def span(self, name: str, attributes: dict[str, AttributeValue] | None = None) -> AbstractContextManager[Span]:
        @contextmanager
        def _open() -> Iterator[Span]:
            try:
                manager = self._tracer.start_as_current_span(
                    name, attributes=attributes or {}, record_exception=False, set_status_on_exception=False
                )
                span = manager.__enter__()
            except Exception as error:  # telemetry must never break a turn
                _log.debug("telemetry_span_failed", error_type=type(error).__name__)
                yield NoopSpan()
                return
            try:
                yield OtelSpanHandle(span)
            except BaseException as raised:
                span.set_attribute("error.type", type(raised).__name__)
                span.set_status(Status(StatusCode.ERROR, type(raised).__name__))
                manager.__exit__(None, None, None)
                raise
            manager.__exit__(None, None, None)

        return _open()

    def _instrument(self, name: str, kind: Kind) -> _Instrument | None:
        existing = self._instruments.get(name)
        if existing is not None:
            return existing
        spec = CATALOG.get(name)
        unit = spec.unit if spec is not None else ""
        description = spec.description if spec is not None else ""
        try:
            if kind is Kind.COUNTER:
                record: Callable[..., None] = self._meter.create_counter(name, unit, description).add
            elif kind is Kind.GAUGE:
                record = self._meter.create_gauge(name, unit, description).set
            else:
                buckets = spec.buckets if spec is not None else None
                histogram = self._meter.create_histogram(
                    name, unit, description, explicit_bucket_boundaries_advisory=buckets
                )
                record = histogram.record
        except Exception as error:  # telemetry must never break startup
            _log.warning("telemetry_instrument_failed", metric=name, error_type=type(error).__name__)
            return None
        instrument = _Instrument(name, record)
        self._instruments[name] = instrument
        return instrument

    def counter(self, name: str) -> Counter:
        return self._instrument(name, Kind.COUNTER) or NoopCounter()

    def histogram(self, name: str) -> Histogram:
        return self._instrument(name, Kind.HISTOGRAM) or NoopHistogram()

    def gauge(self, name: str) -> Gauge:
        return self._instrument(name, Kind.GAUGE) or NoopGauge()

    def current_trace_id(self) -> str | None:
        return trace_id_of(trace.get_current_span())
