"""Inspect the serialized OTLP bytes sent by the Langfuse generation exporter."""

from collections.abc import Iterator, Sequence
from typing import cast

import pytest
import requests
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode

from bank_agent.adapters.llm.tracing import TracingDecorator
from bank_agent.adapters.telemetry import langfuse as langfuse_module
from bank_agent.adapters.telemetry.langfuse import LangfuseGenerationExporter
from bank_agent.adapters.telemetry.opentelemetry import OpenTelemetryAdapter
from bank_agent.domain.errors import LlmRateLimitedError
from bank_agent_llm import StubClient, call_structured


class CaptureSession:
    def __init__(self) -> None:
        self.payloads: list[bytes] = []

    def request(self, method: str, url: str, **kwargs: object) -> requests.Response:
        assert method == "POST"
        assert url.endswith("/api/public/otel/v1/traces")
        data = kwargs["data"]
        assert isinstance(data, bytes)
        self.payloads.append(data)
        response = requests.Response()
        response.status_code = 200
        return response

    def close(self) -> None:
        pass


@pytest.fixture
def capture() -> Iterator[tuple[TracerProvider, CaptureSession]]:
    session = CaptureSession()
    provider = TracerProvider()
    exporter = OTLPSpanExporter(
        endpoint="http://langfuse.local/api/public/otel/v1/traces", session=cast(requests.Session, session)
    )
    provider.add_span_processor(SimpleSpanProcessor(LangfuseGenerationExporter(exporter)))
    yield provider, session
    provider.shutdown()


@pytest.mark.parametrize("failed", [False, True])
def test_outbound_generation_payload_contains_only_approved_metadata(
    capture: tuple[TracerProvider, CaptureSession], failed: bool
) -> None:
    provider, session = capture
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("bank.turn"), tracer.start_as_current_span("gen_ai.chat") as span:
        span.set_attribute("gen_ai.request.model", "openai/test")
        span.set_attribute("bank.prompt.id", "test_prompt")
        span.set_attribute("bank.prompt.version", "1")
        span.set_attribute("bank.correlation_id", "turn-123")
        span.set_attribute("bank.conversation_id", "conversation-123")
        span.set_attribute("gen_ai.usage.input_tokens", 12)
        span.set_attribute("gen_ai.usage.output_tokens", 6)
        span.set_attribute("bank.llm.cost_usd", "0.002")
        span.set_attribute("bank.llm.input_variables", "PRIVATE_CUSTOMER_CONTENT")
        span.set_attribute("bank.llm.output", "PRIVATE_MODEL_REPLY")
        span.set_attribute("bank.tool.payload", "PRIVATE_TOOL_PAYLOAD")
        span.set_attribute("api_key", "PRIVATE_CREDENTIAL")
        span.add_event("PRIVATE_EVENT", {"message": "PRIVATE_EXCEPTION_MESSAGE"})
        if failed:
            span.set_attribute("error.type", "provider_error")
            span.set_status(Status(StatusCode.ERROR, "PRIVATE_EXCEPTION_MESSAGE"))

    assert len(session.payloads) == 1
    payload = session.payloads[0]
    for forbidden in (
        b"PRIVATE_CUSTOMER_CONTENT",
        b"PRIVATE_MODEL_REPLY",
        b"PRIVATE_TOOL_PAYLOAD",
        b"PRIVATE_CREDENTIAL",
        b"PRIVATE_EXCEPTION_MESSAGE",
        b"PRIVATE_EVENT",
    ):
        assert forbidden not in payload
    request = ExportTraceServiceRequest.FromString(payload)
    spans = [span for resource in request.resource_spans for scope in resource.scope_spans for span in scope.spans]
    assert len(spans) == 1
    sent = spans[0]
    attributes = {item.key: item.value for item in sent.attributes}
    assert sent.name == "gen_ai.chat"
    assert not sent.events
    assert attributes["langfuse.observation.type"].string_value == "generation"
    assert attributes["langfuse.observation.metadata.call_id"].string_value
    assert attributes["langfuse.observation.metadata.correlation_id"].string_value == "turn-123"
    assert attributes["langfuse.observation.metadata.conversation_id"].string_value == "conversation-123"
    assert attributes["langfuse.observation.usage_details"].string_value == '{"input": 12, "output": 6, "total": 18}'
    assert attributes["langfuse.observation.cost_details"].string_value == '{"total": 0.002}'
    assert sent.status.message == ""
    if failed:
        assert attributes["langfuse.observation.level"].string_value == "ERROR"
        assert attributes["langfuse.observation.metadata.error_code"].string_value == "provider_error"
    else:
        assert "langfuse.observation.level" not in attributes


def test_export_failure_is_reported_without_interrupting_successful_work(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingExporter(SpanExporter):
        def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
            raise RuntimeError("PRIVATE_EXCEPTION_MESSAGE")

        def shutdown(self) -> None:
            pass

    warnings: list[tuple[str, dict[str, object]]] = []

    class LogCapture:
        def warning(self, event: str, **fields: object) -> None:
            warnings.append((event, fields))

    monkeypatch.setattr(langfuse_module, "_log", LogCapture())
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(LangfuseGenerationExporter(FailingExporter())))
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("gen_ai.chat") as span:
        span.set_attribute("gen_ai.request.model", "openai/test")
    provider.shutdown()
    assert warnings == [("langfuse_export_failed", {"error_type": "RuntimeError", "count": 1})]


@pytest.mark.parametrize("failed", [False, True])
async def test_real_model_decorator_emits_private_free_otlp_payload(
    capture: tuple[TracerProvider, CaptureSession], failed: bool
) -> None:
    provider, session = capture
    telemetry = OpenTelemetryAdapter(provider, MeterProvider())
    error = LlmRateLimitedError("PRIVATE_EXCEPTION_MESSAGE")
    stub = StubClient(outcomes=[error] if failed else ["ok"])
    client = TracingDecorator(
        stub,
        telemetry=telemetry,
        provider_name="anthropic",
        request_model="anthropic/claude-sonnet-5",
        capture_content=True,
    )
    if failed:
        with pytest.raises(LlmRateLimitedError):
            await call_structured(client, variables={"customer_message": "PRIVATE_CUSTOMER_CONTENT"})
    else:
        await call_structured(client, variables={"customer_message": "PRIVATE_CUSTOMER_CONTENT"})
    assert len(session.payloads) == 1
    payload = session.payloads[0]
    assert b"PRIVATE_CUSTOMER_CONTENT" not in payload
    assert b"PRIVATE_EXCEPTION_MESSAGE" not in payload
    request = ExportTraceServiceRequest.FromString(payload)
    (sent,) = [span for resource in request.resource_spans for scope in resource.scope_spans for span in scope.spans]
    attributes = {item.key: item.value for item in sent.attributes}
    assert attributes["langfuse.observation.type"].string_value == "generation"
    assert attributes["langfuse.observation.metadata.status"].string_value == ("error" if failed else "success")
    assert attributes["langfuse.observation.metadata.prompt_id"].string_value == "phrase_response"
    assert attributes["langfuse.observation.metadata.schema_id"].string_value == "SimpleOutput"
    if failed:
        assert attributes["langfuse.observation.metadata.error_code"].string_value == "LlmRateLimitedError"
    else:
        assert attributes["gen_ai.usage.input_tokens"].int_value > 0
        assert attributes["gen_ai.usage.output_tokens"].int_value > 0
