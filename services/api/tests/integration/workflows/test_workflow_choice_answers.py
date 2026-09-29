"""An answer to the workflow question that names a workflow we did not offer (phase 14b, found on the dev split):
the keyword router offered "saldos o tarjetas" for a disputed charge, the customer answered "es sobre un cargo que
no reconozco", and the dispute started from the answer alone, so the amount and merchant of the first message were
lost and the customer was asked for them again. The workflow now starts with both messages."""

import pytest

from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import MX, PT
from bank_agent_workflow_support import Backend, cases
from bank_agent_workflows import build_harness

CONVERSATIONS = {
    MX: ("Hay un cargo en mi tarjeta de 1250 pesos en FIXTURE MARKET que yo no hice",
         "Es sobre un cargo que no reconozco", "no", "sí"),
    PT: ("Tem uma cobrança de 88 pesos na PADARIA BOA no meu cartão que eu não fiz",
         "É sobre uma cobrança que não reconheço", "não", "sim"),
}  # fmt: skip


@pytest.mark.parametrize("customer", [MX, PT])
async def test_an_answer_outside_the_offered_workflows_keeps_the_first_message(backend: Backend, customer: str) -> None:
    first, answer, no_block, confirm = CONVERSATIONS[customer]
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(customer, step_up=True)
    asked = await harness.say(first, session)
    assert asked.response.template_id == "common.clarify_workflow"
    offered = await harness.say(answer, session, asked.conversation_id)
    assert offered.state == "OFFER_PROTECTIVE_BLOCK"
    summary = await harness.say(no_block, session, asked.conversation_id)
    assert summary.state == "CONFIRM_SUMMARY"
    done = await harness.say(confirm, session, asked.conversation_id)
    assert (done.state, done.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert len(await cases(harness, session)) == 1


async def test_an_offered_choice_still_runs_the_first_message(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    asked = await harness.say("necesito ayuda con algo del banco", session)
    assert asked.response.template_id == "common.clarify_workflow"
    chosen = await harness.say("con mis tarjetas", session, asked.conversation_id)
    assert chosen.state in {"CLARIFY", "CARD_STATUS"}


async def test_an_answer_that_names_no_workflow_is_routed_as_a_new_message(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    asked = await harness.say("necesito ayuda con algo del banco", session)
    unrelated = await harness.say("¿qué clima hace en Marte?", session, asked.conversation_id)
    assert unrelated.outcome in {Outcome.ABSTAINED, Outcome.CLARIFIED}
    assert len(await cases(harness, session)) == 0
