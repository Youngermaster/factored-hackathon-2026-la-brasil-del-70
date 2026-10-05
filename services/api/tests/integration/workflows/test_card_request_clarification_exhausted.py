"""A replacement or unblock request whose card is never identified escalates cleanly (QA finding CRD-01).

The which-card budget used to run out with the CRD request rule still decisive and no card request, so the handoff
failed validation, the turn returned HTTP 500, and every later message failed the same way. The handoff now gives
``clarification_exhausted`` with the which-card question open, and the next turn is answered normally."""

import pytest

from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import MX, PT
from bank_agent_workflow_support import Backend, assert_schema_valid
from bank_agent_workflows import build_harness


@pytest.mark.parametrize(
    ("customer", "messages"),
    [
        (MX, ("Necesito reponer mi tarjeta", "la que no sirve", "esa", "esa misma")),
        (PT, ("Meu cartão venceu, preciso de um novo", "o que está vencido", "esse que venceu", "esse mesmo")),
        (MX, ("Quiero desbloquear mi tarjeta", "la que está bloqueada", "esa", "esa misma")),
    ],
)
async def test_an_unidentified_card_request_escalates_as_clarification_exhausted(
    backend: Backend, customer: str, messages: tuple[str, ...]
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(customer)
    reply = await harness.say(messages[0], session)
    for text in messages[1:]:
        if reply.outcome is Outcome.ESCALATED:
            break
        reply = await harness.say(text, session, reply.conversation_id)
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert reply.response.escalation is not None
    handoff = (await harness.handoff(session, reply.response.escalation.handoff_id)).handoff
    assert_schema_valid(handoff)
    assert handoff.escalation_reason.code.value == "clarification_exhausted"
    assert handoff.card_request is None
    assert handoff.open_questions
    after = await harness.say("¿sí?" if customer == MX else "sim?", session, reply.conversation_id)
    assert after.outcome is Outcome.ESCALATED
