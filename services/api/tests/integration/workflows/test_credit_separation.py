"""Credit separation, enforced by the engine: no prompt ever receives the credit profile or the risk estimate, and
phrasing gets only the outcome code, the rendered reasons, and the disclaimer.

These run in process over the real policy pack (the eligibility rules and clauses are not in the unit fixture pack),
with a recording ``FakeLLM`` and model understanding, phrasing, and handoff summaries all switched on.
"""

import json
import tempfile
from decimal import Decimal
from pathlib import Path

from pydantic import JsonValue

from bank_agent.adapters.models.learned_risk import LearnedRiskEstimator
from bank_agent.domain.intelligence import PromptRef
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import T0
from bank_agent_models import RISK_LGBM_ARTIFACT, publish
from bank_agent_scenarios import MX, PT, PT2, scenario_data
from bank_agent_workflow_support import CREDIT_SLOTS, NO_SIGNALS, PHRASE, SIGNALS, Backend
from bank_agent_workflows import build_harness

SUMMARY = PromptRef(prompt_id="summarize_for_handoff", version=1)
FORBIDDEN_NAMES = ("score", "income", "risk", "profile", "estimate", "probability", "utilization", "past_due")


def recording_llm() -> FakeLLM:
    fake = FakeLLM()
    fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS))
    nothing = {"product_of_interest": None, "requested_amount": None, "currency_hint": None,
               "requested_term_months": None, "purpose": None, "declared_monthly_income": None}  # fmt: skip
    fake.script(CREDIT_SLOTS, ScriptedResponse(output=nothing))
    fake.script(PHRASE, ScriptedResponse(output="Uma pessoa da equipe continua com você."))
    summary: dict[str, JsonValue] = {"summary": "El cliente pidió una revisión de crédito.", "cited_fact_ids": ["F1"]}
    fake.script(SUMMARY, ScriptedResponse(output=summary))
    return fake


def forbidden_values() -> set[str]:
    """Every profile value of the fixtures and every probability of the score-band table, as written in prompts."""
    values: set[str] = set()
    for profile in scenario_data().credit_profiles:
        if profile.credit_score is not None:
            values.add(str(profile.credit_score))
        if profile.estimated_monthly_income is not None:
            amount = profile.estimated_monthly_income.amount
            values |= {str(amount), str(amount.normalize()), f"{int(amount):,}", f"{int(amount):,}".replace(",", ".")}
    for probability in ("0.06", "0.02", "0.15", "0.08", "0.26", "0.27", "0.22", "0.33", "0.25", "0.42"):
        values |= {probability, str(Decimal(probability) * 100).rstrip("0").rstrip(".") + " %"}
    return values


async def test_no_prompt_receives_a_profile_or_estimate_value_on_any_credit_path(memory_only: Backend) -> None:
    fake = recording_llm()
    harness = build_harness(memory_only.uow_factory, memory_only.session_store, llm=fake, phrasing=True,
                            handoff_summary=True)  # fmt: skip
    eligible = harness.session(PT, step_up=True)
    first = await harness.say("Sou elegível para um cartão de crédito com limite de 30 mil pesos?", eligible)
    await harness.say("sim", eligible, first.conversation_id)
    await harness.say("sim", eligible, first.conversation_id)
    borderline = harness.session(PT2)
    second = await harness.say("Posso pedir um empréstimo pessoal de 20 milhões de pesos em 36 meses?", borderline)
    await harness.say("sim", borderline, second.conversation_id)
    missing = harness.session(MX)
    await harness.say("Quiero saber si califico para un préstamo personal de 50 mil pesos a 24 meses", missing)
    assert fake.calls
    forbidden = forbidden_values()
    for call in fake.calls:
        dumped = json.dumps(dict(call.variables), ensure_ascii=False, default=str)
        assert not any(value in dumped for value in forbidden), (call.prompt, dumped)
        assert not any(
            part in name for name in call.variables for part in FORBIDDEN_NAMES if name != "customer_message"
        )
    phrased = [call for call in fake.calls if call.prompt == PHRASE and "eligibility_outcome" in call.variables]
    assert {call.variables["eligibility_outcome"] for call in phrased} >= {"indicatively_eligible", "review_required"}
    assert all(set(call.variables) <= {"workflow", "response_kind", "facts", "clause_texts", "customer_message",
                                       "dialect_hint", "eligibility_outcome", "eligibility_reasons", "disclaimer"}
               for call in fake.calls if call.prompt == PHRASE)  # fmt: skip


LEARNED_VALUES = ("0.12", "0.23", "0.38", "0.11", "0.13", "0.22", "0.25", "0.36", "0.41")


async def test_no_prompt_receives_a_learned_estimate_value(memory_only: Backend) -> None:
    """The same credit paths with the learned ``risk_estimator:lgbm`` behind the port (a fixture artifact)."""
    registry = Path(tempfile.mkdtemp(prefix="model-registry-"))
    learned = LearnedRiskEstimator.load(publish(registry, "risk_estimator:lgbm", RISK_LGBM_ARTIFACT),
                                        FixedClock(T0), SequentialIdGenerator())  # fmt: skip
    fake = recording_llm()
    harness = build_harness(memory_only.uow_factory, memory_only.session_store, llm=fake, phrasing=True,
                            handoff_summary=True, risk_estimator=learned)  # fmt: skip
    eligible = harness.session(PT, step_up=True)
    first = await harness.say("Sou elegível para um cartão de crédito com limite de 30 mil pesos?", eligible)
    await harness.say("sim", eligible, first.conversation_id)
    borderline = harness.session(PT2)
    second = await harness.say("Posso pedir um empréstimo pessoal de 20 milhões de pesos em 36 meses?", borderline)
    await harness.say("sim", borderline, second.conversation_id)
    assert fake.calls
    forbidden = forbidden_values() | set(LEARNED_VALUES)
    for call in fake.calls:
        dumped = json.dumps(dict(call.variables), ensure_ascii=False, default=str)
        assert not any(value in dumped for value in forbidden), (call.prompt, dumped)
        assert not any(
            part in name for name in call.variables for part in FORBIDDEN_NAMES if name != "customer_message"
        )
