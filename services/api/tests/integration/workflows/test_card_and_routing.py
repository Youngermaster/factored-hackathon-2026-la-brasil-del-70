"""Card support and routing scenarios 13 to 18, and baseline B0 (scenario 20)."""

from datetime import date

from bank_agent.domain.actions import ToolName
from bank_agent.domain.cards import CardBlockReason
from bank_agent.domain.conversation import ActionDisplayStatus
from bank_agent.domain.locale import Language
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.workflow import Outcome, WorkflowRef
from bank_agent_scenarios import AR, CO, MX, PT
from bank_agent_workflow_support import Backend, assert_schema_valid, cases
from bank_agent_workflows import build_harness


async def test_13_pt_br_card_status_with_two_cards_asks_then_answers_with_expiry(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT)
    first = await harness.say("Qual é a situação do meu cartão?", session)
    assert (first.state, first.outcome) == ("CLARIFY", Outcome.CLARIFIED)
    assert "**** 2468" in first.response.text
    assert "**** 1357" in first.response.text
    answer = await harness.say("o de débito", session, first.conversation_id)
    assert (answer.state, answer.outcome) == ("CARD_STATUS", Outcome.RESOLVED)
    assert "30 de novembro de 2027" in answer.response.text
    assert answer.response.card_status[0].expires_on == date(2027, 11, 30)
    assert answer.response.language is Language.PT


async def test_13b_es_ar_one_card_status_lists_declined_purchases_without_a_reason(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    reply = await harness.say("¿Por qué me rechazaron una compra con mi tarjeta de crédito?", session)
    assert reply.state == "CARD_STATUS"
    assert "GASOLINERA SOL" in reply.response.text
    assert "no indican el motivo" in reply.response.text
    ar = await harness.say("Quiero saber el estado de mi tarjeta", harness.session(AR))
    assert "31 de marzo de 2028" in ar.response.text


async def test_14_es_co_lost_card_is_blocked_with_step_up_verified_and_reasoned(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(CO)
    first = await harness.say("Perdí mi tarjeta, bloquéala por favor", session)
    assert first.state == "CONFIRM_BLOCK"
    assert first.response.card_action_confirmation is not None
    assert first.response.card_action_confirmation.reason is CardBlockReason.LOST
    step_up = await harness.say("sí", session, first.conversation_id)
    assert (step_up.state, step_up.response.step_up_required) == ("EXECUTE", True)
    verified = harness.session(CO, step_up=True, session_id="ses-co-stepped")
    done = await harness.say("listo, ya verifiqué", verified, first.conversation_id,
                             turn="9b2f0d1e-0000-4000-8000-00000000c014")  # fmt: skip
    assert (done.state, done.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert "bloqueamos tu tarjeta de crédito **** 9999" in done.response.text
    assert [s.status for s in done.response.action_statuses] == [ActionDisplayStatus.VERIFIED]
    record = await harness.record(verified, "9b2f0d1e-0000-4000-8000-00000000c014")
    block = next(call for call in record.tool_calls if call.tool is ToolName.BLOCK_CARD)
    assert block.arguments["reason"] == "lost"
    assert block.verification is not None
    assert block.verification.verified is True
    async with harness.uow_factory(verified.access_context()) as uow:
        card = await uow.products.get("PRD-FIXCO-CRED")  # type: ignore[arg-type]
    assert card is not None
    assert card.status is ProductStatus.BLOCKED


async def test_14b_pt_br_stolen_card_block(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT, step_up=True)
    first = await harness.say("Roubaram meu cartão de crédito, quero bloquear", session)
    assert first.state == "CONFIRM_BLOCK"
    done = await harness.say("sim", session, first.conversation_id)
    assert done.outcome is Outcome.RESOLVED
    assert "bloqueamos o seu cartão de crédito **** 2468" in done.response.text


async def test_15_es_mx_unblock_request_is_escalated_with_the_card_request(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    reply = await harness.say("Quiero desbloquear mi tarjeta de débito", session)
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert reply.response.escalation is not None
    handoff = (await harness.handoff(session, reply.response.escalation.handoff_id)).handoff
    assert_schema_valid(handoff)
    assert handoff.escalation_reason.code.value == "card_unblock_requested"
    assert handoff.card_request is not None
    assert str(handoff.card_request.product_ref) == "products:PRD-FIXMX-DEB"
    assert "CRD-ALL-3@1" in [str(ref) for ref in handoff.policy_basis]


async def test_16_pt_br_stolen_card_replacement_offers_the_block_first(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT, step_up=True)
    first = await harness.say("Roubaram meu cartão de crédito, preciso de um novo", session)
    assert first.state == "CONFIRM_BLOCK"
    assert "Antes de passar o seu pedido" in first.response.text
    done = await harness.say("sim", session, first.conversation_id)
    assert (done.state, done.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert [s.status for s in done.response.action_statuses] == [ActionDisplayStatus.VERIFIED]
    assert done.response.escalation is not None
    handoff = (await harness.handoff(session, done.response.escalation.handoff_id)).handoff
    assert handoff.escalation_reason.code.value == "card_replacement_requested"
    assert handoff.actions_taken[0].verification.value == "verified"
    assert_schema_valid(handoff)


async def test_17_a_switch_from_card_status_to_a_charge_asks_then_moves_to_dispute(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX, step_up=True)
    status = await harness.say("Quiero saber el estado de mi tarjeta de crédito", session)
    assert status.state == "CARD_STATUS"
    asked = await harness.say("No reconozco un cargo de 1250 pesos en FIXTURE MARKET", session, status.conversation_id)
    assert (asked.state, asked.outcome) == ("CARD_STATUS", Outcome.CLARIFIED)
    assert "¿Quieres dejarlo y pasar a una reclamación por un cargo?" in asked.response.text
    moved = await harness.say("sí", session, status.conversation_id)
    assert moved.state == "OFFER_PROTECTIVE_BLOCK"
    record = await harness.record(session, moved.turn_id)
    assert record.workflow == WorkflowRef(id="dispute", version=1)
    assert record.workflow_before == WorkflowRef(id="card_support", version=1)


async def test_18_an_investment_request_is_out_of_scope_in_es_and_pt(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    for customer, text, human in ((MX, "Recomiéndame una inversión para mis ahorros", "persona del equipo"),
                                  (PT, "Quero uma recomendação de investimento", "pessoa da equipe")):  # fmt: skip
        reply = await harness.say(text, harness.session(customer))
        assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
        assert human in reply.response.text
        assert {"SCOPE-ALL-1@1", "SCOPE-ALL-2@1"} <= {str(c.clause) for c in reply.response.citations}
        record = await harness.record(harness.session(customer), reply.turn_id)
        assert record.workflow == WorkflowRef(id="router", version=1)


async def test_20_baseline_b0_runs_a_dispute_and_a_card_block_from_its_menu(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX, step_up=True)
    menu = await harness.say("hola", session, baseline=True)
    assert "Menú principal" in menu.response.text
    assert "somente em espanhol" in menu.response.text
    first = await harness.say("reclamar un cargo de 1250 en FIXTURE MARKET", session, menu.conversation_id,
                              baseline=True)  # fmt: skip
    assert first.state == "CLASSIFY_REASON"
    summary = await harness.say("no reconozco", session, menu.conversation_id, baseline=True)
    assert summary.state == "CONFIRM_SUMMARY"
    done = await harness.say("sí", session, menu.conversation_id, baseline=True)
    assert done.outcome is Outcome.RESOLVED
    assert len(await cases(harness, session)) == 1
    other = harness.session(CO, step_up=True)
    block = await harness.say("bloquear tarjeta", other, baseline=True)
    assert block.state == "CONFIRM_BLOCK"
    blocked = await harness.say("sí", other, block.conversation_id, baseline=True)
    assert blocked.outcome is Outcome.RESOLVED
