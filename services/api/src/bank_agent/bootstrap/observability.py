"""OpenTelemetry providers, exporters, sampling, and instrumentation for one process.

``build_observability`` always installs an SDK tracer provider, so spans have trace ids, the API can answer with
``X-Trace-Id``, logs carry the trace id, and execution records store it, even when nothing is exported. With
``OTEL_ENABLED=true`` spans go through a batch processor and metrics through a periodic reader, both over OTLP/HTTP to
``OTEL_EXPORTER_OTLP_ENDPOINT`` (``/v1/traces`` and ``/v1/metrics``). Nothing here sets the OpenTelemetry globals:
each instrumentation receives the providers explicitly, so tests can build as many as they need.

HTTP spans and the ``http.server.request.duration`` histogram follow the stable HTTP semantic conventions
(``OTEL_SEMCONV_STABILITY_OPT_IN=http``). Health probes are not traced.
"""

import os
from base64 import b64encode
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from sqlalchemy.ext.asyncio import AsyncEngine

from bank_agent import __version__
from bank_agent.adapters.telemetry.langfuse import LangfuseGenerationExporter
from bank_agent.adapters.telemetry.opentelemetry import OpenTelemetryAdapter
from bank_agent.bootstrap.settings import LangfuseSettings, ObservabilitySettings

EXCLUDED_URLS: Final = "/health/live,/health/ready,/health/details"
STABILITY_OPT_IN: Final = "OTEL_SEMCONV_STABILITY_OPT_IN"


@dataclass
class Observability:
    """The telemetry adapter and the providers behind it."""

    telemetry: OpenTelemetryAdapter
    tracer_provider: TracerProvider
    meter_provider: MeterProvider
    exporting: bool
    _instrumented: list[str] = field(default_factory=list)

    def instrument_app(self, app: FastAPI) -> None:
        """Server spans and HTTP metrics for every route except the health probes."""
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=self.tracer_provider,
            meter_provider=self.meter_provider,
            excluded_urls=EXCLUDED_URLS,
            exclude_spans=["receive", "send"],
        )
        self._instrumented.append("fastapi")

    def instrument_dependencies(self, engine: AsyncEngine | None) -> None:
        """SQLAlchemy and httpx spans, only when exporting (httpx instrumentation patches the library globally)."""
        if not self.exporting:
            return
        if engine is not None:
            # The instrumentation declares sqlalchemy < 2.1 but works with 2.1 through the engine events it uses;
            # the phase 15 obs run checked that database spans reach Jaeger (docs/operations/observability.md).
            SQLAlchemyInstrumentor().instrument(
                engine=engine.sync_engine,
                tracer_provider=self.tracer_provider,
                meter_provider=self.meter_provider,
                skip_dep_check=True,
                enable_commenter=False,
            )
            self._instrumented.append("sqlalchemy")
        HTTPXClientInstrumentor().instrument(tracer_provider=self.tracer_provider, meter_provider=self.meter_provider)
        self._instrumented.append("httpx")

    @property
    def instrumented(self) -> tuple[str, ...]:
        return tuple(self._instrumented)

    def shutdown(self) -> None:
        """Flush and stop the exporters (called once when the application stops)."""
        if "httpx" in self._instrumented:
            HTTPXClientInstrumentor().uninstrument()
        self.tracer_provider.shutdown()
        self.meter_provider.shutdown()


def build_observability(
    settings: ObservabilitySettings,
    *,
    langfuse: LangfuseSettings | None = None,
    environment: str = "development",
    span_processors: Sequence[SpanProcessor] = (),
    metric_readers: Sequence[MetricReader] = (),
) -> Observability:
    """Providers for ``settings``; tests add in-memory processors and readers instead of exporting."""
    os.environ.setdefault(STABILITY_OPT_IN, "http")
    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": __version__,
            "deployment.environment.name": environment,
        }
    )
    tracer_provider = TracerProvider(
        resource=resource, sampler=ParentBased(TraceIdRatioBased(settings.traces_sampler_arg))
    )
    readers: list[MetricReader] = list(metric_readers)
    endpoint = settings.exporter_otlp_endpoint.rstrip("/")
    if settings.enabled:
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
        readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
                export_interval_millis=settings.metric_export_interval,
            )
        )
    if langfuse is not None and langfuse.enabled:
        if langfuse.public_key is None or langfuse.secret_key is None:
            raise ValueError("Langfuse export requires both keys")
        credentials = f"{langfuse.public_key.get_secret_value()}:{langfuse.secret_key.get_secret_value()}"
        authorization = b64encode(credentials.encode("utf-8")).decode("ascii")
        exporter = OTLPSpanExporter(
            endpoint=f"{langfuse.base_url.rstrip('/')}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {authorization}", "x-langfuse-ingestion-version": "4"},
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(LangfuseGenerationExporter(exporter)))
    for processor in span_processors:
        tracer_provider.add_span_processor(processor)
    meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    return Observability(
        telemetry=OpenTelemetryAdapter(tracer_provider, meter_provider),
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        exporting=settings.enabled,
    )
