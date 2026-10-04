"""Chaos: the language model fails (provider errors, timeouts) until the circuit opens, then the budget runs out.

Every turn still gets a safe answer from the deterministic path; once the circuit is open (L2) no call is attempted,
the reply says the service is limited, in es and pt, and the execution record names why; the half-open trial closes
the circuit again when the provider answers.
"""

from datetime import timedelta

import pytest

from bank_agent.domain.errors import LlmProviderError, LlmTimeoutError
from bank_agent.domain.intelligence import PromptRef, TokenUsage
from bank_agent.testing.fake_llm import FakeLLM, ScriptedError, ScriptedResponse
from bank_agent_api import ApiBackend, ApiClient
from bank_agent_chaos import LIMITED_ES, LIMITED_PT, staff_records
from bank_agent_workflow_support import ACCOUNT_SLOTS, NO_SIGNALS, SIGNALS

MODEL_PROMPTS = (SIGNALS, ACCOUNT_SLOTS)
ACCOUNT_OUTPUT = {"product_hint": None, "statement_period_expression": None, "payment": None}


def _failing(*errors: type[LlmProviderError] | type[LlmTimeoutError]) -> FakeLLM:
    fake = FakeLLM()
    for prompt in MODEL_PROMPTS:
        fake.script(prompt, *(ScriptedError(error) for error in errors))
    return fake


@pytest.fixture
def reliability_environment(memory_api: ApiBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    """Model understanding on, no retries, and a circuit that opens after two failures (after ``memory_api``)."""
    monkeypatch.setenv("WORKFLOW_LLM_UNDERSTANDING", "true")
    monkeypatch.setenv("LLM_MAX_RETRIES", "0")
    monkeypatch.setenv("LLM_CIRCUIT_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("LLM_CIRCUIT_RESET_SECONDS", "30")


def _codes(record: dict[str, object]) -> list[str]:
    calls = record["llm_calls"]
    assert isinstance(calls, list)
    return [str(call["error_code"]) for call in calls if call["status"] == "fallback"]


@pytest.mark.usefixtures("reliability_environment")
async def test_provider_errors_open_the_circuit_and_turns_become_template_only_in_es_and_pt(
    memory_api: ApiBackend,
) -> None:
    fake = _failing(LlmProviderError)
    harness = memory_api.build(llm=fake)
    async with ApiClient(harness.app) as client:
        await client.login("persona-mx")
        conversation = await client.open_conversation()
        first = await client.say(conversation, "¿Cuál es mi saldo?")
        assert first.status_code == 200, first.text
        assert LIMITED_ES not in first.json()["message"]["text"]
        calls_before = len(fake.calls)
        details = (await client.get("/health/details")).json()
        assert (details["level"], details["reasons"], details["template_only"]) == ("L2", ["llm_unavailable"], True)

        second = await client.say(conversation, "¿Cuál es mi saldo?")
        assert second.status_code == 200
        assert second.json()["message"]["text"].startswith(LIMITED_ES)
        assert second.json()["outcome"] in {"resolved", "clarified", "escalated"}
        assert len(fake.calls) == calls_before

    async with ApiClient(harness.app, client_ip="203.0.113.21") as portuguese:
        await portuguese.login("persona-pt")
        pt_conversation = await portuguese.open_conversation()
        reply = await portuguese.say(pt_conversation, "Qual é o meu saldo?")
        assert reply.status_code == 200
        assert reply.json()["message"]["text"].startswith(LIMITED_PT)

    async with ApiClient(harness.app, client_ip="203.0.113.22") as evaluator:
        records = await staff_records(evaluator, conversation)
    first_record, second_record = records[first.json()["turn_id"]], records[second.json()["turn_id"]]
    assert set(_codes(first_record)) == {"llm_provider_error"}
    assert set(_codes(second_record)) == {"degraded_template_only"}
    assert {"llm_fallback", "degradation_l2"} <= set(second_record["safety_interventions"])
    assert second_record["trace_id"] is None or len(second_record["trace_id"]) == 32
    assert second_record["state_after"]
    assert second_record["latency"]["total_ms"] >= 0
    assert all(status["status"] != "verified" for status in second.json()["message"]["action_statuses"])


@pytest.mark.usefixtures("reliability_environment")
async def test_timeouts_open_the_circuit_and_a_successful_trial_closes_it(
    memory_api: ApiBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "0.05")
    fake = FakeLLM()
    for prompt in MODEL_PROMPTS:
        fake.script(prompt, ScriptedError(LlmTimeoutError))
    harness = memory_api.build(llm=fake)
    async with ApiClient(harness.app) as client:
        await client.login("persona-mx")
        conversation = await client.open_conversation()
        await client.say(conversation, "¿Cuál es mi saldo?")
        assert (await client.get("/health/details")).json()["level"] == "L2"
        fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS))
        fake.script(ACCOUNT_SLOTS, ScriptedResponse(output=ACCOUNT_OUTPUT))
        harness.clock.advance(timedelta(seconds=31))
        details = (await client.get("/health/details")).json()
        assert (details["level"], details["components"]["llm_primary"]) == ("L0", "degraded")
        trial = await client.say(conversation, "¿Cuál es mi saldo?")
        assert trial.status_code == 200
        assert not trial.json()["message"]["text"].startswith(LIMITED_ES)
        assert (await client.get("/health/details")).json()["components"]["llm_primary"] == "ok"


@pytest.mark.usefixtures("reliability_environment")
async def test_the_spent_daily_budget_switches_to_template_only_until_the_next_day(
    memory_api: ApiBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD", "0.01")
    fake = FakeLLM()
    # 600 output tokens of an unlisted model at the highest listed price times 1.5 cost 0.009 USD, the reservation.
    usage = TokenUsage(input_tokens=0, output_tokens=600)
    fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS, usage=usage))
    fake.script(ACCOUNT_SLOTS, ScriptedResponse(output=ACCOUNT_OUTPUT, usage=usage))
    harness = memory_api.build(llm=fake)
    async with ApiClient(harness.app) as client:
        await client.login("persona-mx")
        conversation = await client.open_conversation()
        spent = await client.say(conversation, "¿Cuál es mi saldo?")
        assert spent.status_code == 200
        details = (await client.get("/health/details")).json()
        assert (details["level"], details["reasons"], details["budget_used_ratio"]) == (
            "L2",
            ["llm_budget_exhausted"],
            0.9,
        )
        assert details["components"]["llm_budget"] == "unavailable"
        limited = await client.say(conversation, "¿Cuál es mi saldo?")
        assert limited.json()["message"]["text"].startswith(LIMITED_ES)
        harness.clock.advance(timedelta(days=1))
        assert (await client.get("/health/details")).json()["level"] == "L0"
    async with ApiClient(harness.app, client_ip="203.0.113.23") as evaluator:
        records = await staff_records(evaluator, conversation)
    assert _codes(records[spent.json()["turn_id"]]) == ["llm_budget_exceeded"]
    assert set(_codes(records[limited.json()["turn_id"]])) == {"degraded_template_only"}


def test_the_model_prompts_are_the_ones_a_balance_turn_calls() -> None:
    assert {str(prompt) for prompt in MODEL_PROMPTS} == {
        str(PromptRef(prompt_id="detect_escalation_signals", version=2)),
        str(PromptRef(prompt_id="extract_account_inquiry_slots", version=1)),
    }
