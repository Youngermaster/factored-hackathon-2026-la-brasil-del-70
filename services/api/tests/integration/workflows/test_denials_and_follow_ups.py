"""Denials explained by clauses, already-blocked cards, card follow-ups, and a dispute already open."""

from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import CO, MX, PT
from bank_agent_workflow_support import Backend
from bank_agent_workflows import build_harness


async def test_an_already_blocked_card_abstains_with_the_clause(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    reply = await harness.say("Quiero bloquear mi tarjeta de débito", harness.session(MX))
    assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
    assert "ya está bloqueada" in reply.response.text
    assert reply.response.citations


async def test_a_follow_up_after_card_status_blocks_the_same_card(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    session = harness.session(CO, step_up=True)
    status = await harness.say("¿Cuál es el estado de mi tarjeta?", session)
    assert status.state == "CARD_STATUS"
    confirm = await harness.say("mejor bloquéala, creo que la perdí", session, status.conversation_id)
    assert confirm.state == "CONFIRM_BLOCK"
    declined = await harness.say("no", session, status.conversation_id)
    assert (declined.state, declined.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert "no registré nada" in declined.response.text


async def test_a_transaction_with_an_open_dispute_is_denied_with_the_clause(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    reply = await harness.say("No recibí lo que compré en LIBRERIA BOGOTA por 42.000 pesos", harness.session(CO))
    assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
    assert "No puedo registrar esta reclamación aquí" in reply.response.text
    assert any(str(c.clause).startswith("DSP-ALL-4") for c in reply.response.citations)


async def test_a_declined_purchase_cannot_be_disputed(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    reply = await harness.say("No reconozco un cargo de 200 pesos en GASOLINERA SOL", harness.session(MX))
    assert reply.outcome is Outcome.ABSTAINED
    assert any(str(c.clause).startswith("DSP-ALL-1") for c in reply.response.citations)


async def test_pt_br_a_customer_without_the_named_card_gets_the_choice(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    reply = await harness.say("Quero bloquear meu cartão terminado em 0000", harness.session(PT))
    assert reply.state in {"CLARIFY", "CONFIRM_BLOCK"}
