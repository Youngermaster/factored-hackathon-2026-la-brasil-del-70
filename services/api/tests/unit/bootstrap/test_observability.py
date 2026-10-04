"""Observability composition: export off by default, OTLP/HTTP when enabled, sampling, and trace ids in logs."""

import io
import json

import structlog
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import SecretStr

from bank_agent.adapters.telemetry.langfuse import LangfuseGenerationExporter
from bank_agent.bootstrap.logging import configure_logging
from bank_agent.bootstrap.observability import build_observability
from bank_agent.bootstrap.settings import LangfuseSettings, ObservabilitySettings


def _processors(observability: object) -> list[object]:
    active = observability.tracer_provider._active_span_processor  # type: ignore[attr-defined]
    return list(active._span_processors)


def test_nothing_is_exported_unless_enabled() -> None:
    observability = build_observability(ObservabilitySettings())
    try:
        assert not observability.exporting
        assert _processors(observability) == []
        with observability.telemetry.span("bank.turn") as span:
            assert span.trace_id is not None
    finally:
        observability.shutdown()


def test_enabled_exports_traces_and_metrics_over_otlp_http() -> None:
    settings = ObservabilitySettings(enabled=True, exporter_otlp_endpoint="http://collector.invalid:4318/")
    observability = build_observability(settings)
    try:
        (processor,) = _processors(observability)
        assert isinstance(processor, BatchSpanProcessor)
        exporter = processor._batch_processor._exporter
        assert isinstance(exporter, OTLPSpanExporter)
        assert exporter._endpoint == "http://collector.invalid:4318/v1/traces"
        readers = observability.meter_provider._metric_readers
        (reader,) = readers
        assert isinstance(reader, PeriodicExportingMetricReader)
        assert isinstance(reader._exporter, OTLPMetricExporter)
        assert reader._exporter._endpoint == "http://collector.invalid:4318/v1/metrics"
    finally:
        observability.shutdown()


def test_langfuse_disabled_creates_no_exporter_even_with_keys() -> None:
    langfuse = LangfuseSettings(
        enabled=False, public_key=SecretStr("public-test"), secret_key=SecretStr("private-test")
    )
    observability = build_observability(ObservabilitySettings(enabled=False), langfuse=langfuse)
    try:
        assert _processors(observability) == []
        assert not observability.meter_provider._metric_readers
    finally:
        observability.shutdown()


def test_langfuse_enabled_uses_the_existing_trace_provider() -> None:
    langfuse = LangfuseSettings(
        enabled=True,
        base_url="http://langfuse.invalid:3000/",
        public_key=SecretStr("public-test"),
        secret_key=SecretStr("private-test"),
    )
    observability = build_observability(ObservabilitySettings(enabled=False), langfuse=langfuse)
    try:
        (processor,) = _processors(observability)
        assert isinstance(processor, BatchSpanProcessor)
        exporter = processor._batch_processor._exporter
        assert isinstance(exporter, LangfuseGenerationExporter)
        assert isinstance(exporter._inner, OTLPSpanExporter)
        assert exporter._inner._endpoint == "http://langfuse.invalid:3000/api/public/otel/v1/traces"
        assert not observability.meter_provider._metric_readers
    finally:
        observability.shutdown()


def test_a_zero_ratio_samples_nothing_but_keeps_trace_ids() -> None:
    exporter = InMemorySpanExporter()
    observability = build_observability(
        ObservabilitySettings(traces_sampler_arg=0.0), span_processors=[SimpleSpanProcessor(exporter)]
    )
    try:
        with observability.telemetry.span("bank.turn") as span:
            assert span.trace_id is not None
        assert exporter.get_finished_spans() == ()
    finally:
        observability.shutdown()


def test_the_resource_names_the_service_version_and_environment() -> None:
    observability = build_observability(ObservabilitySettings(service_name="bank-agent-test"), environment="test")
    try:
        attributes = observability.tracer_provider.resource.attributes
        assert attributes["service.name"] == "bank-agent-test"
        assert attributes["deployment.environment.name"] == "test"
        assert attributes["service.version"]
    finally:
        observability.shutdown()


def test_log_lines_inside_a_span_carry_its_trace_and_span_ids_unredacted() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)
    observability = build_observability(ObservabilitySettings())
    try:
        with observability.telemetry.span("bank.turn") as span:
            structlog.get_logger("test").info("turn_completed", customer_email="ana@example.com")
        (record,) = [json.loads(line) for line in stream.getvalue().splitlines()]
    finally:
        observability.shutdown()
    assert record["trace_id"] == span.trace_id
    assert len(str(record["span_id"])) == 16
    assert record["customer_email"] == "[REDACTED]"


def test_a_forged_trace_field_is_still_redacted() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)
    structlog.get_logger("test").info("odd", trace_id="ana@example.com", span_id="12345678901")
    (record,) = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert record["trace_id"] == "[REDACTED:email]"
    assert record["span_id"] == "[REDACTED:number]"
