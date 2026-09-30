"""One span per call, with OpenTelemetry GenAI semantic convention attributes.

Attribute names follow the OpenTelemetry semantic conventions for generative AI, version 1.37.0
(``GENAI_SEMCONV_VERSION``); the phase 15 OpenTelemetry adapter sets the matching schema URL. Spans go through the
``Telemetry`` port, whose span names are dot-separated, so the span is named ``gen_ai.chat`` rather than the
convention's ``chat {model}``; the operation and model are attributes. Project-specific attributes use the
``bank.`` prefix.

Content capture is off by default. When enabled (``LLM_TRACE_CONTENT=true``, never in production), the span
also carries the canonical JSON of the variables, which the outer redaction decorator has already scrubbed,
and the output.
"""

import hashlib
import json
import time
from collections.abc import Callable
from typing import Final

from bank_agent.adapters.llm.request import Generation, LlmDecorator, LlmRequest, Proceed
from bank_agent.domain.errors import LlmError
from bank_agent.domain.intelligence import TextGeneration, canonical_variables
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.telemetry import AttributeValue, Telemetry

GENAI_SEMCONV_VERSION: Final = "1.37.0"
SPAN_NAME: Final = "gen_ai.chat"
DURATION_METRIC: Final = "gen_ai.client.operation.duration"
USAGE_METRIC: Final = "gen_ai.client.token.usage"


class TracingDecorator(LlmDecorator):
    """Opens a ``gen_ai.chat`` span per call and records duration and token usage histograms."""

    def __init__(
        self,
        inner: LLMClient,
        *,
        telemetry: Telemetry,
        provider_name: str,
        request_model: str,
        capture_content: bool = False,
        monotonic: Callable[[], float] = time.perf_counter,
    ) -> None:
        super().__init__(inner)
        self.telemetry = telemetry
        self.provider_name = provider_name
        self.request_model = request_model
        self.capture_content = capture_content
        self._monotonic = monotonic
        self._duration = telemetry.histogram(DURATION_METRIC)
        self._tokens = telemetry.histogram(USAGE_METRIC)

    def _request_attributes(self, request: LlmRequest) -> dict[str, AttributeValue]:
        attributes: dict[str, AttributeValue] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": self.provider_name,
            "gen_ai.request.model": self.request_model,
            "gen_ai.request.max_tokens": request.max_output_tokens,
            "gen_ai.request.temperature": request.temperature,
            "gen_ai.output.type": "json" if request.structured else "text",
            "bank.prompt.id": request.prompt.prompt_id,
            "bank.prompt.version": request.prompt.version,
            "bank.language": request.language.value,
        }
        if request.call_context.turn_id is not None:
            attributes["bank.correlation_id"] = request.call_context.turn_id
        if request.call_context.conversation_id is not None:
            attributes["bank.conversation_id"] = request.call_context.conversation_id
        if request.output_model is not None:
            schema = request.output_model.model_json_schema()
            digest = hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            attributes["bank.schema.id"] = request.output_model.__name__
            attributes["bank.schema.version"] = digest[:12]
            attributes["bank.schema.hash"] = digest
        return attributes

    async def around(self, request: LlmRequest, proceed: Proceed) -> Generation:
        attributes = self._request_attributes(request)
        metric_attributes: dict[str, AttributeValue] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": self.provider_name,
            "gen_ai.request.model": self.request_model,
        }
        with self.telemetry.span(SPAN_NAME, attributes) as span:
            if self.capture_content:
                span.set_attribute("bank.llm.input_variables", canonical_variables(request.variables))
            started = self._monotonic()
            try:
                result = await proceed(request)
            except LlmError as error:
                span.set_attribute("bank.llm.status", "error")
                span.set_attribute("bank.llm.latency_ms", max(0, round((self._monotonic() - started) * 1000)))
                span.set_attribute("error.type", error.code)
                span.record_error_code(error.code)
                self._duration.record(self._monotonic() - started, {**metric_attributes, "error.type": error.code})
                raise
            self._duration.record(self._monotonic() - started, metric_attributes)
            span.set_attribute("bank.llm.status", "success")
            span.set_attribute("gen_ai.response.model", result.model_id)
            if result.provider_model_id is not None:
                span.set_attribute("bank.provider.returned_model_id", result.provider_model_id)
            span.set_attribute("gen_ai.usage.input_tokens", result.usage.input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", result.usage.output_tokens)
            span.set_attribute("bank.llm.latency_ms", result.latency_ms)
            if result.cost_usd is not None:
                span.set_attribute("bank.llm.cost_usd", str(result.cost_usd))
            if not isinstance(result, TextGeneration):
                span.set_attribute("bank.llm.repaired", result.repaired)
            if self.capture_content:
                output = (
                    result.text
                    if isinstance(result, TextGeneration)
                    else json.dumps(result.value.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
                )
                span.set_attribute("bank.llm.output", output)
            self._tokens.record(result.usage.input_tokens, {**metric_attributes, "gen_ai.token.type": "input"})
            self._tokens.record(result.usage.output_tokens, {**metric_attributes, "gen_ai.token.type": "output"})
            return result
