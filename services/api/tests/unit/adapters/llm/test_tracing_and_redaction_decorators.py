import hashlib
import json
from decimal import Decimal

import pytest

from bank_agent.adapters.llm.redaction import RedactionDecorator, Redactor
from bank_agent.adapters.llm.tracing import (
    DURATION_METRIC,
    GENAI_SEMCONV_VERSION,
    SPAN_NAME,
    USAGE_METRIC,
    TracingDecorator,
)
from bank_agent.domain.errors import LlmRateLimitedError
from bank_agent.domain.intelligence import LlmCallContext
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_llm import SimpleOutput, StubClient, call_structured, call_text


class Ticks:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        self.value += 0.25
        return self.value


def _tracer(stub: StubClient, telemetry: RecordingTelemetry, *, capture: bool = False) -> TracingDecorator:
    return TracingDecorator(
        stub,
        telemetry=telemetry,
        provider_name="anthropic",
        request_model="anthropic/claude-sonnet-5",
        capture_content=capture,
        monotonic=Ticks(),
    )


async def test_span_carries_genai_request_and_response_attributes() -> None:
    telemetry = RecordingTelemetry()
    stub = StubClient(model_id="anthropic/claude-sonnet-5", cost_usd=Decimal("0.0021"))

    generation = await call_structured(_tracer(stub, telemetry), max_output_tokens=321)

    (span,) = telemetry.spans
    assert generation.model_call_id == span.span_id
    assert span.name == SPAN_NAME
    schema_hash = hashlib.sha256(
        json.dumps(SimpleOutput.model_json_schema(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert span.attributes == {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "anthropic",
        "gen_ai.request.model": "anthropic/claude-sonnet-5",
        "gen_ai.request.max_tokens": 321,
        "gen_ai.request.temperature": 0.0,
        "gen_ai.output.type": "json",
        "bank.prompt.id": "phrase_response",
        "bank.prompt.version": 1,
        "bank.language": "es",
        "bank.schema.id": "SimpleOutput",
        "bank.schema.version": schema_hash[:12],
        "bank.schema.hash": schema_hash,
        "bank.llm.status": "success",
        "gen_ai.response.model": "anthropic/claude-sonnet-5",
        "gen_ai.usage.input_tokens": 1000,
        "gen_ai.usage.output_tokens": 200,
        "bank.llm.latency_ms": 5,
        "bank.llm.cost_usd": "0.0021",
        "bank.llm.repaired": False,
    }
    assert telemetry.histograms[DURATION_METRIC].values[0][0] == 0.25
    usage = telemetry.histograms[USAGE_METRIC].values
    assert [(value, attributes["gen_ai.token.type"]) for value, attributes in usage] == [
        (1000, "input"),
        (200, "output"),
    ]
    assert GENAI_SEMCONV_VERSION == "1.37.0"


async def test_content_is_not_captured_by_default() -> None:
    telemetry = RecordingTelemetry()

    await call_text(_tracer(StubClient(), telemetry), variables={"customer_message": "texto privado"})

    (span,) = telemetry.spans
    assert span.attributes["gen_ai.output.type"] == "text"
    assert "bank.llm.repaired" not in span.attributes
    assert not any("privado" in str(value) for value in span.attributes.values())
    assert "bank.llm.cost_usd" not in span.attributes


async def test_content_capture_records_variables_and_output_when_enabled() -> None:
    telemetry = RecordingTelemetry()
    tracer = _tracer(StubClient(), telemetry, capture=True)

    await call_text(tracer, variables={"customer_message": "hola"})
    await call_structured(tracer, variables={"customer_message": "hola"})

    text_span, structured_span = telemetry.spans
    assert text_span.attributes["bank.llm.input_variables"] == '{"customer_message":"hola"}'
    assert text_span.attributes["bank.llm.output"] == "hola"
    assert structured_span.attributes["bank.llm.output"] == '{"answer": "yes"}'


async def test_failures_record_the_error_type() -> None:
    telemetry = RecordingTelemetry()

    with pytest.raises(LlmRateLimitedError):
        await call_structured(_tracer(StubClient(outcomes=[LlmRateLimitedError()]), telemetry))

    (span,) = telemetry.spans
    assert span.attributes["error.type"] == "llm_rate_limited"
    assert span.error_codes == ["llm_rate_limited"]
    assert telemetry.histograms[DURATION_METRIC].values[0][1]["error.type"] == "llm_rate_limited"


async def test_redaction_decorator_scrubs_non_allowlisted_variables_before_the_inner_client() -> None:
    stub = StubClient()
    client = RedactionDecorator(stub, redactor=Redactor())
    context = LlmCallContext(sensitive_terms=("Rosa",))

    await call_text(
        client,
        variables={"customer_message": "Soy Rosa, mi correo es rosa@example.com", "dialect_hint": "es-CO"},
        context=context,
    )

    assert stub.calls[0]["variables"] == {
        "customer_message": "Soy [NAME], mi correo es [EMAIL]",
        "dialect_hint": "es-CO",
    }
