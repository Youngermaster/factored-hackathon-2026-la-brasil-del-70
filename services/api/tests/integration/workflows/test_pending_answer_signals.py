"""A plain yes to a pending confirmation is resolved deterministically (phase 14b): the local model read "Sí, quiero
solicitarlo" after an indicatively eligible answer as a request for a person, and P escalated an intake the customer
wanted to record. The scripted model below reproduces that false signal on every call after the first; the plain
answers never reach it, while a real request at the same step still does."""

import pytest

from bank_agent.domain.errors import LlmProviderError
from bank_agent.domain.workflow import Outcome
from bank_agent.testing.fake_llm import FakeLLM, ScriptedError, ScriptedResponse, scripted_calls
from bank_agent_scenarios import PT
from bank_agent_workflow_support import CREDIT_SLOTS, NO_SIGNALS, SIGNALS, Backend
from bank_agent_workflows import build_harness

FALSE_HUMAN = {**NO_SIGNALS, "human_requested": True}
ASK = {
    "es": "¿Soy elegible para una tarjeta de crédito con límite de 30 mil pesos?",
    "pt": "Sou elegível para um cartão de crédito com limite de 30 mil pesos?",
}
YES_APPLY = {"es": "Sí, quiero solicitarlo", "pt": "Sim, quero solicitar"}
YES = {"es": "sí", "pt": "sim"}


def _model_that_reads_yes_as_a_person() -> FakeLLM:
    fake = FakeLLM()
    fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS), ScriptedResponse(output=FALSE_HUMAN))
    fake.script(CREDIT_SLOTS, ScriptedError(LlmProviderError))
    return fake


@pytest.mark.parametrize("language", ["es", "pt"])
async def test_a_plain_yes_to_the_intake_offer_records_the_intake(backend: Backend, language: str) -> None:
    fake = _model_that_reads_yes_as_a_person()
    harness = build_harness(backend.uow_factory, backend.session_store, llm=fake)
    session = harness.session(PT, step_up=True)
    explained = await harness.say(ASK[language], session)
    assert (explained.state, explained.outcome) == ("EXPLAIN_ELIGIBILITY", Outcome.RESOLVED)
    confirm = await harness.say(YES_APPLY[language], session, explained.conversation_id)
    assert confirm.state == "CONFIRM_INTAKE"
    assert confirm.response.escalation is None
    done = await harness.say(YES[language], session, explained.conversation_id)
    assert (done.state, done.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert done.response.action_statuses[0].status.value == "verified"
    assert len(scripted_calls(fake, SIGNALS)) == 1


async def test_a_request_for_a_person_at_the_same_step_still_reaches_the_model(backend: Backend) -> None:
    fake = _model_that_reads_yes_as_a_person()
    harness = build_harness(backend.uow_factory, backend.session_store, llm=fake)
    session = harness.session(PT, step_up=True)
    explained = await harness.say(ASK["pt"], session)
    asked = await harness.say("prefiro que alguém do banco cuide disso", session, explained.conversation_id)
    assert (asked.state, asked.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert len(scripted_calls(fake, SIGNALS)) == 2


async def test_a_plain_yes_with_a_keyword_request_for_a_person_still_escalates(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT, step_up=True)
    explained = await harness.say(ASK["pt"], session)
    asked = await harness.say("sim, quero falar com um atendente", session, explained.conversation_id)
    assert (asked.state, asked.outcome) == ("ESCALATED", Outcome.ESCALATED)
