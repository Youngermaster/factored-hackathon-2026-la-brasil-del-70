"""Allowlisted OTLP export of LLM spans to Langfuse.

The regular LiteLLM callback is deliberately absent: it includes messages and provider
payloads. This exporter reconstructs each generation from approved scalar attributes,
discarding events, links, exception messages, input, output, and all other span data.
"""

import json
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import Final

import structlog
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult, SpanExporter
from opentelemetry.trace import Status, StatusCode

_log = structlog.get_logger(__name__)
GENERATION_SPAN: Final = "gen_ai.chat"
_COPY: Final[dict[str, str]] = {
    "gen_ai.provider.name": "gen_ai.provider.name",
    "gen_ai.request.model": "gen_ai.request.model",
    "gen_ai.response.model": "gen_ai.response.model",
    "bank.provider.returned_model_id": "langfuse.observation.metadata.provider_returned_model_id",
    "gen_ai.usage.input_tokens": "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens": "gen_ai.usage.output_tokens",
    "bank.llm.latency_ms": "langfuse.observation.metadata.latency_ms",
    "bank.prompt.id": "langfuse.observation.metadata.prompt_id",
    "bank.prompt.version": "langfuse.observation.metadata.prompt_version",
    "bank.schema.id": "langfuse.observation.metadata.schema_id",
    "bank.schema.version": "langfuse.observation.metadata.schema_version",
    "bank.schema.hash": "langfuse.observation.metadata.schema_hash",
    "bank.correlation_id": "langfuse.observation.metadata.correlation_id",
    "bank.conversation_id": "langfuse.observation.metadata.conversation_id",
    "bank.llm.status": "langfuse.observation.metadata.status",
    "error.type": "langfuse.observation.metadata.error_code",
}


class LangfuseGenerationExporter(SpanExporter):
    """Send only generation spans through an OTLP exporter, after a strict field allowlist."""

    def __init__(self, inner: SpanExporter) -> None:
        self._inner = inner

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        safe: list[ReadableSpan] = []
        for span in spans:
            if span.name != GENERATION_SPAN or span.context is None or not span.context.is_valid:
                continue
            source = span.attributes or {}
            attributes: dict[str, str | int | float | bool] = {
                "langfuse.observation.type": "generation",
                "langfuse.observation.metadata.call_id": format(span.context.span_id, "016x"),
                "langfuse.observation.metadata.trace_id": format(span.context.trace_id, "032x"),
            }
            for source_key, target_key in _COPY.items():
                value = source.get(source_key)
                if isinstance(value, str | int | float | bool):
                    attributes[target_key] = value
            # Langfuse accepts JSON strings for usage and cost. The fields above are
            # also kept as GenAI attributes for other OTLP consumers.
            input_tokens = source.get("gen_ai.usage.input_tokens")
            output_tokens = source.get("gen_ai.usage.output_tokens")
            if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                attributes["langfuse.observation.usage_details"] = json.dumps(
                    {"input": input_tokens, "output": output_tokens, "total": input_tokens + output_tokens}
                )
            cost = source.get("bank.llm.cost_usd")
            if isinstance(cost, str):
                try:
                    amount = Decimal(cost)
                except InvalidOperation:
                    amount = None
                if amount is not None and amount.is_finite() and amount >= 0:
                    attributes["langfuse.observation.cost_details"] = json.dumps({"total": float(amount)})
            if span.status.status_code is StatusCode.ERROR:
                attributes["langfuse.observation.level"] = "ERROR"
                attributes.setdefault("langfuse.observation.metadata.status", "error")
            safe.append(
                ReadableSpan(
                    name=GENERATION_SPAN,
                    context=span.context,
                    parent=span.parent,
                    resource=Resource.create({"service.name": "bank-agent-api"}),
                    attributes=attributes,
                    events=(),
                    links=(),
                    kind=span.kind,
                    status=Status(span.status.status_code),
                    start_time=span.start_time,
                    end_time=span.end_time,
                    instrumentation_scope=span.instrumentation_scope,
                )
            )
        if not safe:
            return SpanExportResult.SUCCESS
        try:
            result = self._inner.export(safe)
        except Exception as error:
            _log.warning("langfuse_export_failed", error_type=type(error).__name__, count=len(safe))
            return SpanExportResult.FAILURE
        if result is not SpanExportResult.SUCCESS:
            _log.warning("langfuse_export_failed", error_type="ExportFailure", count=len(safe))
        return result

    def shutdown(self) -> None:
        self._inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._inner.force_flush(timeout_millis=timeout_millis)
