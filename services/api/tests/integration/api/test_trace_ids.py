"""One trace per request: ``X-Trace-Id``, the exported spans, and the execution record all name the same trace."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from bank_agent.asgi import build_app
from bank_agent.bootstrap.observability import build_observability
from bank_agent.bootstrap.settings import load_settings
from bank_agent.testing.clock import FixedClock
from bank_agent_api import ApiClient, api_environment, memory_persistence
from bank_agent_scenarios import NOW


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
