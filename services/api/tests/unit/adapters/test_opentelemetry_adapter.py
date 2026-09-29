"""The OpenTelemetry adapter against in-memory exporters: spans, the schema URL, metrics, and failure isolation."""

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricsData
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF
from opentelemetry.trace import StatusCode

from bank_agent.adapters.telemetry.catalog import CATALOG
from bank_agent.adapters.telemetry.noop import NoopTelemetry
from bank_agent.adapters.telemetry.opentelemetry import SCHEMA_URL, OpenTelemetryAdapter


@dataclass
class Rig:
    telemetry: OpenTelemetryAdapter
    spans: InMemorySpanExporter
    metrics: InMemoryMetricReader


@pytest.fixture
def rig() -> Iterator[Rig]:
    spans = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(spans))
    reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[reader])
    yield Rig(OpenTelemetryAdapter(tracer_provider, meter_provider), spans, reader)
    tracer_provider.shutdown()
    meter_provider.shutdown()


def _points(data: MetricsData | None, name: str) -> list[tuple[dict[str, object], object]]:
    assert data is not None
    found: list[tuple[dict[str, object], object]] = []
    for resource in data.resource_metrics:
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                if metric.name == name:
                    found.extend((dict(point.attributes or {}), point) for point in metric.data.data_points)
    return found


def test_spans_nest_and_carry_attributes_and_the_genai_schema_url(rig: Rig) -> None:
    with (
        rig.telemetry.span("bank.turn", {"bank.workflow": "dispute"}) as turn,
        rig.telemetry.span("bank.tool", {"bank.tool": "get_transaction"}) as tool,
    ):
        tool.set_attribute("bank.tool.status", "ok")
        assert rig.telemetry.current_trace_id() == turn.trace_id
    child, parent = rig.spans.get_finished_spans()
    assert parent.name == "bank.turn"
    assert child.name == "bank.tool"
    assert child.parent is not None
    assert child.parent.span_id == parent.context.span_id
    assert child.attributes == {"bank.tool": "get_transaction", "bank.tool.status": "ok"}
    assert parent.instrumentation_scope is not None
    assert parent.instrumentation_scope.schema_url == SCHEMA_URL == "https://opentelemetry.io/schemas/1.37.0"
    assert turn.trace_id is not None
    assert len(turn.trace_id) == 32


def test_an_error_inside_a_span_propagates_and_marks_only_its_type(rig: Rig) -> None:
    with pytest.raises(ValueError, match="customer text never reaches the span"), rig.telemetry.span("bank.turn"):
        raise ValueError("customer text never reaches the span")
    (span,) = rig.spans.get_finished_spans()
    assert span.status.status_code is StatusCode.ERROR
    assert span.attributes == {"error.type": "ValueError"}
    assert not span.events


def test_record_error_code_sets_the_error_type_and_status(rig: Rig) -> None:
    with rig.telemetry.span("gen_ai.chat") as span:
        span.record_error_code("timeout")
    (finished,) = rig.spans.get_finished_spans()
    assert finished.status.status_code is StatusCode.ERROR
    assert finished.attributes is not None
    assert finished.attributes["error.type"] == "timeout"


def test_no_trace_id_outside_a_span(rig: Rig) -> None:
    assert rig.telemetry.current_trace_id() is None


def test_an_unsampled_span_still_has_a_trace_id() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_OFF)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    telemetry = OpenTelemetryAdapter(provider, MeterProvider())
    with telemetry.span("bank.turn") as span:
        assert span.trace_id is not None
    assert exporter.get_finished_spans() == ()


def test_counters_histograms_and_gauges_use_the_catalog_units(rig: Rig) -> None:
    rig.telemetry.counter("bank.turn.outcomes").add(2, {"bank.workflow": "credit", "bank.outcome": "resolved"})
    rig.telemetry.histogram("bank.turn.duration").record(0.2, {"bank.workflow": "credit"})
    rig.telemetry.gauge("bank.degradation.level").set(2)
    data = rig.metrics.get_metrics_data()
    ((attributes, counter),) = _points(data, "bank.turn.outcomes")
    assert attributes == {"bank.workflow": "credit", "bank.outcome": "resolved"}
    assert getattr(counter, "value") == 2  # noqa: B009
    ((_, histogram),) = _points(data, "bank.turn.duration")
    assert list(getattr(histogram, "explicit_bounds")) == list(CATALOG["bank.turn.duration"].buckets or ())  # noqa: B009
    ((_, gauge),) = _points(data, "bank.degradation.level")
    assert getattr(gauge, "value") == 2  # noqa: B009
    units = {
        metric.name: metric.unit
        for resource in (data.resource_metrics if data else ())
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }
    assert units["bank.turn.duration"] == "s"


def test_a_broken_instrument_never_raises(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    counter = rig.telemetry.counter("bank.escalations")

    def explode(*_: object, **__: object) -> None:
        raise RuntimeError("exporter down")

    monkeypatch.setattr(counter, "_record", explode)
    counter.add(1)
    counter.add(1)


def test_a_broken_tracer_yields_a_span_that_does_nothing(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_: object, **__: object) -> None:
        raise RuntimeError("tracer down")

    monkeypatch.setattr(rig.telemetry._tracer, "start_as_current_span", explode)
    with rig.telemetry.span("bank.turn") as span:
        span.set_attribute("bank.workflow", "dispute")
        assert span.trace_id is None


def test_the_noop_adapter_implements_the_same_surface() -> None:
    noop = NoopTelemetry()
    with noop.span("bank.turn") as span:
        span.record_error_code("x")
    noop.gauge("bank.degradation.level").set(1)
    assert noop.current_trace_id() is None
