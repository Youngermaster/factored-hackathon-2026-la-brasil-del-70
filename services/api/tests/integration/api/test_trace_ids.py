"""One trace per request: ``X-Trace-Id``, the exported spans, and the execution record all name the same trace."""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from bank_agent.adapters.telemetry import langfuse as langfuse_module
from bank_agent.adapters.telemetry.langfuse import LangfuseGenerationExporter
from bank_agent.asgi import build_app
from bank_agent.bootstrap.llm import LlmOverrides
from bank_agent.bootstrap.observability import build_observability
from bank_agent.bootstrap.settings import load_settings
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_api import ApiClient, api_environment, memory_persistence
from bank_agent_scenarios import NOW
from bank_agent_workflow_support import ACCOUNT_SLOTS, NO_SIGNALS, SIGNALS


@dataclass
class Traced:
    app: FastAPI
    client: ApiClient
    spans: InMemorySpanExporter


@pytest.fixture
async def traced(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Traced]:
    api_environment(monkeypatch)
    settings = load_settings(env_file=None)
    spans = InMemorySpanExporter()
    observability = build_observability(settings.observability, span_processors=[SimpleSpanProcessor(spans)])
    app = build_app(settings, observability, clock=FixedClock(NOW), persistence=memory_persistence())
    async with app.router.lifespan_context(app), ApiClient(app) as client:
        yield Traced(app, client, spans)


def _names_by_trace(spans: InMemorySpanExporter, trace_id: str) -> list[str]:
    return [span.name for span in spans.get_finished_spans() if format(span.context.trace_id, "032x") == trace_id]


async def test_a_turn_response_names_the_trace_its_execution_record_stores(traced: Traced) -> None:
    await traced.client.login("persona-mx")
    conversation = await traced.client.open_conversation()
    response = await traced.client.say(conversation, "¿Cuál es mi saldo?")
    assert response.status_code == 200, response.text
    trace_id = response.headers["X-Trace-Id"]
    assert len(trace_id) == 32

    async with ApiClient(traced.app, client_ip="203.0.113.20") as evaluator:
        await evaluator.login("persona-evaluator")
        trace = await evaluator.get(f"/v1/eval/conversations/{conversation}/trace")
    (record,) = trace.json()["records"]
    assert record["trace_id"] == trace_id
    names = _names_by_trace(traced.spans, trace_id)
    assert {"bank.turn", "bank.router.dispatch", "bank.workflow.state", "bank.tool.call"} <= set(names)
    assert any(name.startswith("POST /v1/conversations") for name in names)


async def test_every_traced_response_carries_its_own_trace_id(traced: Traced) -> None:
    first = await traced.client.get("/v1/auth/csrf")
    second = await traced.client.get("/v1/auth/csrf")
    assert first.headers["X-Trace-Id"] != second.headers["X-Trace-Id"]
    assert "X-Trace-Id" not in (await traced.client.get("/health/live")).headers


async def test_the_state_and_tool_spans_carry_ids_and_codes_only(traced: Traced) -> None:
    await traced.client.login("persona-mx")
    conversation = await traced.client.open_conversation()
    response = await traced.client.say(conversation, "¿Cuál es mi saldo?")
    trace_id = response.headers["X-Trace-Id"]
    finished = [s for s in traced.spans.get_finished_spans() if format(s.context.trace_id, "032x") == trace_id]
    state = next(s for s in finished if s.name == "bank.workflow.state")
    assert state.attributes is not None
    assert state.attributes["bank.workflow"] == "account_inquiry"
    tool = next(s for s in finished if s.name == "bank.tool.call")
    assert tool.attributes is not None
    assert tool.attributes["bank.tool.status"] == "ok"
    for span in finished:
        for value in (span.attributes or {}).values():
            assert "saldo" not in str(value)


async def test_langfuse_export_failure_is_logged_without_failing_a_customer_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingExporter(SpanExporter):
        def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
            raise RuntimeError("private exporter detail")

        def shutdown(self) -> None:
            pass

    warnings: list[tuple[str, dict[str, object]]] = []

    class LogCapture:
        def warning(self, event: str, **fields: object) -> None:
            warnings.append((event, fields))

    monkeypatch.setattr(langfuse_module, "_log", LogCapture())
    api_environment(monkeypatch, WORKFLOW_LLM_UNDERSTANDING="true")
    settings = load_settings(env_file=None)
    llm = FakeLLM()
    llm.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS))
    llm.script(
        ACCOUNT_SLOTS,
        ScriptedResponse(output={"product_hint": None, "statement_period_expression": None, "payment": None}),
    )
    captured = InMemorySpanExporter()
    observability = build_observability(
        settings.observability,
        span_processors=[
            SimpleSpanProcessor(LangfuseGenerationExporter(FailingExporter())),
            SimpleSpanProcessor(captured),
        ],
    )
    app = build_app(
        settings,
        observability,
        clock=FixedClock(NOW),
        persistence=memory_persistence(),
        llm_overrides=LlmOverrides(primary=llm),
    )
    async with app.router.lifespan_context(app):
        async with ApiClient(app) as client:
            await client.login("persona-ar")
            conversation = await client.open_conversation()
            response = await client.say(conversation, "Hola, ¿me decís cuál es mi saldo?")
        async with ApiClient(app, client_ip="203.0.113.20") as evaluator:
            await evaluator.login("persona-evaluator")
            trace = await evaluator.get(f"/v1/eval/conversations/{conversation}/trace")
        span_ids = {
            format(span.context.span_id, "016x") for span in captured.get_finished_spans() if span.name == "gen_ai.chat"
        }
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "resolved"
    assert llm.calls
    (record,) = trace.json()["records"]
    model_call_ids = {call["model_call_id"] for call in record["llm_calls"] if call["status"] == "ok"}
    assert model_call_ids == span_ids
    assert model_call_ids
    assert warnings
    assert all(
        event == "langfuse_export_failed" and fields["error_type"] == "RuntimeError" for event, fields in warnings
    )
    assert "private exporter detail" not in str(warnings)
