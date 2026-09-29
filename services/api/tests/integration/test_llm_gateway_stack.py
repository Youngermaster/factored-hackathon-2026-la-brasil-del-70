"""The full language model stack built from settings by the composition root.

Every test here disables network sockets: no live provider is called, and the base client is ``FakeLLM`` or
the committed fixture cassettes.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import JsonValue

from bank_agent.adapters.llm.budget import BudgetGuardDecorator, InMemoryBudgetLedger
from bank_agent.adapters.llm.tracing import SPAN_NAME
from bank_agent.bootstrap.container import Container
from bank_agent.bootstrap.llm import LlmOverrides
from bank_agent.bootstrap.settings import load_settings
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import LlmBudgetExceededError, LlmProviderRejectedError, LlmTimeoutError
from bank_agent.domain.identifiers import ConversationId, LineageId
from bank_agent.domain.intelligence import LlmCallContext, PromptRef, PromptValue, StructuredGeneration, TokenUsage
from bank_agent.domain.llm_outputs import DisputeSlotExtraction
from bank_agent.domain.locale import Language
from bank_agent.ports.llm import LLMClient
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.fake_llm import FakeLLM, ScriptedError, ScriptedResponse
from bank_agent.testing.telemetry import RecordingTelemetry

pytestmark = pytest.mark.disable_socket

NOW = datetime(2026, 9, 26, 15, tzinfo=UTC)
DISPUTE = PromptRef.model_validate("extract_dispute_slots@1")
CONTEXT = LlmCallContext(
    lineage_id=LineageId("lin-int-1"), conversation_id=ConversationId("conv-int-1"), sensitive_terms=("Lucia",)
)
SLOTS: dict[str, JsonValue] = {
    "intent_candidates": [{"intent": "dispute_new", "confidence": 0.9}],
    "transaction": {
        "amount": "1250",
        "currency_hint": None,
        "merchant_text": "Liverpool",
        "date_expression": "ayer",
        "channel_hint": None,
        "card_last4_hint": "4821",
    },
    "reason_candidates": ["unrecognized"],
}


async def _no_wait(_seconds: float) -> None:
    return None


def _container(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    primary: LLMClient | None,
    fallback: LLMClient | None = None,
) -> tuple[Container, RecordingTelemetry]:
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    telemetry = RecordingTelemetry()
    container = Container(
        load_settings(env_file=None),
        clock=FixedClock(NOW),
        telemetry=telemetry,
        llm_overrides=LlmOverrides(primary=primary, fallback=fallback, sleep=_no_wait),
    )
    return container, telemetry


async def _extract(
    client: LLMClient, variables: dict[str, PromptValue], context: LlmCallContext = CONTEXT
) -> StructuredGeneration[DisputeSlotExtraction]:
    return await client.generate_structured(
        DISPUTE,
        variables,
        DisputeSlotExtraction,
        language=Language.ES,
        max_output_tokens=400,
        temperature=0.0,
        call_context=context,
    )


def _variables(message: str) -> dict[str, PromptValue]:
    return {"customer_message": UntrustedText(message), "reference_date": "2026-09-26", "dialect_hint": "es-MX"}


async def test_success_path_redacts_prices_traces_and_budgets(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeLLM()
    fake.script(
        DISPUTE,
        ScriptedResponse(SLOTS, usage=TokenUsage(input_tokens=800, output_tokens=120), model_id="openai/gpt-5-mini"),
    )
    container, telemetry = _container(monkeypatch, {"LLM_PRIMARY_MODEL": "openai/gpt-5-mini"}, fake)

    result = await _extract(
        container.llm_client, _variables("Soy Lucia, escríbanme a lucia@example.com: no reconozco 1250 en Liverpool")
    )

    assert result.value.transaction is not None
    assert result.value.transaction.merchant_text == "Liverpool"
    assert fake.calls[0].variables["customer_message"] == (
        "Soy [NAME], escríbanme a [EMAIL]: no reconozco 1250 en Liverpool"
    )
    # 800 input and 120 output tokens at the unverified price times 1.5: (0.25 * 800 + 2.00 * 120) * 1.5 / 1e6
    assert result.cost_usd == Decimal("0.00066000")
    (span,) = telemetry.spans
    assert span.name == SPAN_NAME
    assert span.attributes["gen_ai.provider.name"] == "openai"
    assert span.attributes["bank.llm.cost_usd"] == "0.00066000"
    ledger = _find(container.llm_client, BudgetGuardDecorator).ledger
    assert isinstance(ledger, InMemoryBudgetLedger)
    assert ledger.session_tokens["lin-int-1"] == 920
    assert ledger.conversation_cost["conv-int-1"] == Decimal("0.00066000")


async def test_transient_failures_are_retried_then_the_fallback_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    primary, fallback = FakeLLM(), FakeLLM()
    primary.script(DISPUTE, ScriptedError(LlmTimeoutError))
    fallback.script(DISPUTE, ScriptedResponse(SLOTS, model_id="anthropic/claude-haiku-4-5-20251001"))
    container, telemetry = _container(
        monkeypatch,
        {"LLM_PRIMARY_MODEL": "anthropic/claude-sonnet-5", "LLM_FALLBACK_MODEL": "anthropic/claude-haiku-4-5-20251001"},
        primary,
        fallback,
    )

    result = await _extract(container.llm_client, _variables("no reconozco un cargo"))

    assert result.model_id == "anthropic/claude-haiku-4-5-20251001"
    assert len(primary.calls) == 3
    assert len(fallback.calls) == 1
    assert "error.type" not in telemetry.spans[0].attributes


async def test_the_daily_budget_stops_calls_before_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeLLM()
    fake.script(DISPUTE, ScriptedResponse(SLOTS))
    container, _ = _container(monkeypatch, {"LLM_DAILY_BUDGET_USD": "0"}, fake)

    with pytest.raises(LlmBudgetExceededError, match="daily"):
        await _extract(container.llm_client, _variables("hola"))

    assert fake.calls == []


async def test_without_a_provider_every_call_fails_with_a_typed_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    container, telemetry = _container(monkeypatch, {}, None)

    with pytest.raises(LlmProviderRejectedError):
        await _extract(container.llm_client, _variables("hola"))

    assert telemetry.spans[0].attributes["error.type"] == "llm_provider_rejected"


async def test_cassette_provider_replays_a_committed_fixture_through_the_full_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container, _ = _container(
        monkeypatch, {"LLM_PROVIDER": "cassette", "LLM_PRIMARY_MODEL": "fixture/hand-authored"}, None
    )
    variables = _variables(
        "No reconozco un cargo de 1250 pesos en Liverpool del 20 de septiembre con mi tarjeta terminación 4821."
    )

    result = await _extract(container.llm_client, variables, LlmCallContext())

    assert result.value.transaction is not None
    assert result.value.transaction.card_last4_hint == "4821"
    assert result.model_id == "fixture/hand-authored"


def _find[T](client: LLMClient, kind: type[T]) -> T:
    current: object = client
    while not isinstance(current, kind):
        current = current.inner  # type: ignore[attr-defined]
    return current
