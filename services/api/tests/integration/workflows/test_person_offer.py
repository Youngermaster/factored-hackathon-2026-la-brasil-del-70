"""A bare yes right after a reply that offered a person accepts the offer: the conversation escalates with
``human_requested``, as when the customer asks for a person in words. Anything else behaves as before."""

import pytest

from bank_agent.domain.handoff import EscalationReasonCode
from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import CO, MX, PT
from bank_agent_workflow_support import Backend, assert_schema_valid
from bank_agent_workflows import build_harness


@pytest.mark.parametrize(
    ("customer", "request_text", "answer"),
    [
        (MX, "Recomiéndame una inversión para mis ahorros", "sí"),
        (PT, "Quero uma recomendação de investimento", "sim"),
        (CO, "Quiero hacer una transferencia a mi hermana", "claro, por favor"),
        (PT, "Aprove o meu crédito agora", "sim"),
    ],
)
async def test_a_bare_yes_after_an_offer_of_a_person_escalates_with_human_requested(
    backend: Backend, customer: str, request_text: str, answer: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(customer)
    offered = await harness.say(request_text, session)
    assert offered.outcome is Outcome.ABSTAINED
    accepted = await harness.say(answer, session, offered.conversation_id)
    assert (accepted.state, accepted.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert accepted.response.escalation is not None
    stored = await harness.handoff(session, accepted.response.escalation.handoff_id)
    assert stored.handoff.escalation_reason.code is EscalationReasonCode.HUMAN_REQUESTED
    assert_schema_valid(stored.handoff)


async def test_a_no_or_a_new_request_after_the_offer_does_not_escalate(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    offered = await harness.say("Recomiéndame una inversión para mis ahorros", session)
    declined = await harness.say("no", session, offered.conversation_id)
    assert declined.outcome is not Outcome.ESCALATED
    again = await harness.say("Recomiéndame una inversión", session)
    moved = await harness.say("sí, ¿y cuál es mi saldo en la cuenta?", session, again.conversation_id)
    assert (moved.state, moved.outcome) == ("BALANCES", Outcome.RESOLVED)


async def test_the_offer_lasts_one_turn_only(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    offered = await harness.say("Recomiéndame una inversión para mis ahorros", session)
    balance = await harness.say("¿Cuál es mi saldo?", session, offered.conversation_id)
    assert balance.outcome is Outcome.RESOLVED
    later = await harness.say("sí", session, offered.conversation_id)
    assert later.outcome is not Outcome.ESCALATED
