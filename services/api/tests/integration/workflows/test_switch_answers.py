"""Answers to the engine's switch question (QA finding DSP-08): asking to go on with the pending dispute keeps it,
a yes that names the offered workflow switches, and an unrelated long yes gets the question again."""

import pytest

from bank_agent_scenarios import MX, PT
from bank_agent_workflow_support import Backend
from bank_agent_workflows import Harness, build_harness

DISPUTE = {MX: "No reconozco un cargo de 1250 pesos en FIXTURE MARKET del 15 de junio",
           PT: "Não reconheço uma compra de 88 pesos na PADARIA BOA"}  # fmt: skip
BALANCE = {MX: "¿Cuál es mi saldo?", PT: "Qual é o meu saldo?"}


async def _asked_to_switch(harness: Harness, customer: str) -> tuple[object, str]:
    session = harness.session(customer, step_up=True)
    first = await harness.say(DISPUTE[customer], session)
    assert first.state == "OFFER_PROTECTIVE_BLOCK"
    asked = await harness.say(BALANCE[customer], session, first.conversation_id)
    assert asked.state == "OFFER_PROTECTIVE_BLOCK"
    assert asked.response.template_id == "common.switch_confirm"
    return session, str(first.conversation_id)


@pytest.mark.parametrize(
    ("customer", "text"),
    [
        (MX, "Listo, sigamos con lo del cargo de FIXTURE MARKET"),
        (MX, "Listo, sigamos con lo del cargo"),
        (PT, "Beleza, vamos continuar com a cobrança"),
    ],
)
async def test_asking_to_continue_the_dispute_at_the_switch_question_keeps_the_dispute(
    backend: Backend, customer: str, text: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session, conversation = await _asked_to_switch(harness, customer)
    reply = await harness.say(text, session, conversation)  # type: ignore[arg-type]
    assert reply.state == "OFFER_PROTECTIVE_BLOCK"
    assert reply.workflow is not None
    assert reply.workflow.id == "dispute"
    assert reply.response.balances == ()


@pytest.mark.parametrize(
    ("customer", "text"),
    [(MX, "Sí, quiero ver mi saldo"), (PT, "Sim, pode me mostrar o saldo da minha conta agora")],
)
async def test_a_yes_that_names_the_offered_workflow_switches(backend: Backend, customer: str, text: str) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session, conversation = await _asked_to_switch(harness, customer)
    reply = await harness.say(text, session, conversation)  # type: ignore[arg-type]
    assert reply.state == "BALANCES"
    assert reply.response.balances


async def test_an_unrelated_long_yes_asks_again_and_keeps_the_original_request(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session, conversation = await _asked_to_switch(harness, MX)
    reply = await harness.say("Ok, pero antes déjame pensar otra cosa un momento", session, conversation)  # type: ignore[arg-type]
    assert reply.state == "OFFER_PROTECTIVE_BLOCK"
    assert reply.response.template_id == "common.switch_confirm"
    switched = await harness.say("sí", session, conversation)  # type: ignore[arg-type]
    assert switched.state == "BALANCES"
    assert switched.response.balances
