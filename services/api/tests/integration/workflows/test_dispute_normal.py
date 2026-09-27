"""Dispute scenarios 1 to 4 and 12: normal and ambiguous paths in es-MX, es-AR, pt-BR, and es-CO."""

from datetime import timedelta

from bank_agent.domain.actions import ToolName
from bank_agent.domain.conversation import ActionDisplayStatus
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.execution_record import LlmCallStatus
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Outcome, WorkflowRef
from bank_agent_scenarios import AR, CO, MX, PT
from bank_agent_workflow_support import Backend, cases, scripted_llm
from bank_agent_workflows import build_harness

EXTRACTION = {
    "intent_candidates": [{"intent": "dispute_new", "confidence": 0.93}],
    "transaction": {"amount": "1250", "currency_hint": "MXN", "merchant_text": "FIXTURE MARKET",
                    "date_expression": "el 15 de junio", "channel_hint": None, "card_last4_hint": None},
    "reason_candidates": ["unrecognized"],
}  # fmt: skip


async def test_1_a_normal_es_mx_dispute_is_created_verified_and_reported(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store, llm=scripted_llm(dispute=EXTRACTION))
    session = harness.session(MX, step_up=True)
    first = await harness.say("No reconozco un cargo de 1250 pesos en FIXTURE MARKET del 15 de junio", session)
    assert first.state == "OFFER_PROTECTIVE_BLOCK"
    assert first.response.language is Language.ES
    summary = await harness.say("no, gracias", session, first.conversation_id)
    assert summary.state == "CONFIRM_SUMMARY"
    assert summary.response.confirmation is not None
    assert summary.response.confirmation.reason is DisputeReason.UNRECOGNIZED
    assert "1,250.00 MXN" in summary.response.text
    done = await harness.say("sí", session, first.conversation_id, turn="9b2f0d1e-0000-4000-8000-00000000c001")
    assert (done.state, done.outcome) == ("RESOLVED", Outcome.RESOLVED)
    created = await cases(harness, session)
    assert len(created) == 1
    assert created[0].case_id in done.response.text
    assert "2 de agosto de 2026" in done.response.text
    assert [s.status for s in done.response.action_statuses] == [ActionDisplayStatus.VERIFIED]
    record = await harness.record(session, "9b2f0d1e-0000-4000-8000-00000000c001")
    writes = [call for call in record.tool_calls if call.tool is ToolName.CREATE_DISPUTE_CASE]
    assert writes[0].verification is not None
    assert writes[0].verification.verified is True
    assert record.grounding.violations == ()
    assert record.workflow == WorkflowRef(id="dispute", version=1)
    assert any(str(ref).startswith("INF-ALL-1") for ref in record.clause_refs)
    assert record.policy_pack_version.startswith("pack-")
    first_record = await harness.record(session, first.turn_id)
    assert [call.status for call in first_record.llm_calls] == [LlmCallStatus.OK, LlmCallStatus.OK]
    assert {str(prompt) for prompt in first_record.prompts} == {
        "detect_escalation_signals@1",
        "extract_dispute_slots@1",
    }
    assert {str(model) for model in first_record.models} >= {"router:keyword@1", "resolver:rules@1"}


async def test_1b_a_normal_pt_br_dispute_runs_on_the_deterministic_fallback(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT, step_up=True)
    first = await harness.say("Não reconheço uma compra de 88 pesos na PADARIA BOA", session)
    assert first.state == "OFFER_PROTECTIVE_BLOCK"
    assert first.response.language is Language.PT
    assert "Quer que eu bloqueie" in first.response.text
    summary = await harness.say("não", session, first.conversation_id)
    assert "Confirma?" in summary.response.text
    done = await harness.say("sim", session, first.conversation_id)
    assert done.outcome is Outcome.RESOLVED
    assert "registramos sua contestação" in done.response.text
    record = await harness.record(session, first.turn_id)
    assert {call.status for call in record.llm_calls} == {LlmCallStatus.FALLBACK}
    assert "llm_fallback" in record.safety_interventions


async def test_2_es_ar_voseo_and_lucas_resolve_the_amount(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(AR, step_up=True)
    first = await harness.say(
        "Che, me cobraron 15 lucas en el super el martes pasado y no fui yo, ¿me ayudás?", session
    )
    assert first.state == "OFFER_PROTECTIVE_BLOCK"
    summary = await harness.say("no", session, first.conversation_id)
    assert "15.000,00 ARS" in summary.response.text
    assert summary.response.confirmation is not None
    assert str(summary.response.confirmation.amount.amount) == "15000.00"
    done = await harness.say("dale", session, first.conversation_id)
    assert done.outcome is Outcome.RESOLVED
    assert [case.transaction_id for case in await cases(harness, session)] == ["TRX-FIXAR-0001"]


async def test_3_pt_br_two_similar_transactions_are_clarified_then_resolved(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT, step_up=True)
    first = await harness.say("Não reconheço uma compra de 499 na LOJA AZUL", session)
    assert (first.state, first.outcome) == ("CLARIFY", Outcome.CLARIFIED)
    assert first.response.clarification is not None
    options = first.response.clarification.options
    assert len(options) == 2
    assert {option.card_last4 for option in options} == {"2468"}
    chosen = await harness.say("a segunda", session, first.conversation_id)
    assert chosen.state == "OFFER_PROTECTIVE_BLOCK"
    await harness.say("não", session, first.conversation_id)
    done = await harness.say("sim, pode", session, first.conversation_id)
    assert done.outcome is Outcome.RESOLVED
    assert [case.transaction_id for case in await cases(harness, session)] == ["TRX-FIXPT-0001"]


async def test_3b_es_co_an_ambiguous_day_and_month_is_asked_first(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(CO, step_up=True)
    first = await harness.say("No reconozco un cargo del 05/06 en TIENDA ANDINA", session)
    assert first.state == "CLARIFY"
    assert "6 de mayo de 2026" in first.response.text
    assert "5 de junio de 2026" in first.response.text
    located = await harness.say("el de junio", session, first.conversation_id)
    assert located.state == "OFFER_PROTECTIVE_BLOCK"


async def test_4_es_co_status_inquiry_answers_with_the_sla(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(CO)
    reply = await harness.say("¿Cómo va mi reclamo?", session)
    assert (reply.state, reply.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert "case-fixco000001" in reply.response.text
    assert "abierto" in reply.response.text
    assert [str(c.clause) for c in reply.response.citations][:1] == ["DSP-CO-2@2"]


async def test_4b_an_open_case_past_its_sla_is_escalated(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    harness.clock.advance(timedelta(days=6))
    session = harness.session(CO)
    reply = await harness.say("Quiero saber el estado de mi reclamación", session)
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    record = await harness.record(session, reply.turn_id)
    assert any("DSP.case_within_sla" in d.decisive_rule_ids for d in record.decisions)
    assert record.handoff_ref is not None
    handoff = await harness.handoff(session, record.handoff_ref)
    assert handoff.handoff.escalation_reason.code.value == "sla_breached"


async def test_12_a_declined_protective_block_leaves_the_dispute_going(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(CO, step_up=True)
    first = await harness.say("No reconozco un cargo de 85.000 pesos en TIENDA ANDINA", session)
    assert first.state == "OFFER_PROTECTIVE_BLOCK"
    summary = await harness.say("no", session, first.conversation_id)
    assert summary.response.confirmation is not None
    assert [a.value for a in summary.response.confirmation.planned_actions] == ["create_dispute_case"]
    done = await harness.say("sí", session, first.conversation_id, turn="9b2f0d1e-0000-4000-8000-00000000c012")
    assert done.outcome is Outcome.RESOLVED
    record = await harness.record(session, "9b2f0d1e-0000-4000-8000-00000000c012")
    assert ToolName.BLOCK_CARD not in [call.tool for call in record.tool_calls]
    async with harness.uow_factory(session.access_context()) as uow:
        card = await uow.products.get("PRD-FIXCO-CRED")  # type: ignore[arg-type]
    assert card is not None
    assert card.status.value == "active"
