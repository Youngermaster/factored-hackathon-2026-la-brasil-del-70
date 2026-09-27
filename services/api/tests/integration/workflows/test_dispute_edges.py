"""Dispute scenarios 5 to 11 and replay: unsupported requests, escalations, expiry, isolation, failures, injection."""

from datetime import timedelta

from bank_agent.application.engine.idempotency import derive_key
from bank_agent.domain.actions import ActionKind, ToolFailureMode, ToolName
from bank_agent.domain.complaint import Priority
from bank_agent.domain.conversation import NoticeCode
from bank_agent.domain.execution_record import ToolCallStatus
from bank_agent.domain.handoff import VerificationStatus
from bank_agent.domain.identifiers import SourceRef
from bank_agent.domain.trust import RiskTier, TrustEventKind
from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import AR, INJECTION_MERCHANT, MX, PT
from bank_agent_workflow_support import Backend, assert_no_transcript, assert_schema_valid, cases
from bank_agent_workflows import build_harness

OPENING = "No reconozco un cargo de 1250 pesos en FIXTURE MARKET del 15 de junio"


async def test_5_a_limit_increase_is_abstained_with_the_scope_clause_in_es_and_pt(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    for customer, text, offer in ((MX, "Quiero un aumento de límite de mi tarjeta", "persona del equipo"),
                                  (PT, "Quero um aumento de limite do meu cartão", "pessoa da equipe")):  # fmt: skip
        reply = await harness.say(text, harness.session(customer))
        assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
        assert offer in reply.response.text
        cited = [str(citation.clause) for citation in reply.response.citations]
        assert "SCOPE-ALL-2@1" in cited
        record = await harness.record(harness.session(customer), reply.turn_id)
        assert any("SCOPE.supported_intent" in d.decisive_rule_ids for d in record.decisions)
        assert "out_of_scope" in record.safety_interventions


async def test_6_a_regulator_mention_escalates_with_a_schema_valid_handoff(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    text = "No reconozco un cargo de 1250 pesos y voy a poner una queja en la CONDUSEF"
    reply = await harness.say(text, session)
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert reply.response.escalation is not None
    stored = await harness.handoff(session, reply.response.escalation.handoff_id)
    handoff = stored.handoff
    assert_schema_valid(handoff)
    assert_no_transcript(handoff, "CONDUSEF", text)
    assert handoff.escalation_reason.code.value == "legal_or_regulator_mention"
    assert handoff.priority is Priority.HIGH
    assert "ESC-MX-2@1" in [str(ref) for ref in handoff.policy_basis]
    assert handoff.sla_due == harness.clock.now() + timedelta(hours=24)


async def test_6b_pt_br_a_human_request_mid_dispute_escalates(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT)
    first = await harness.say("Não reconheço uma compra de 499 na LOJA AZUL", session)
    assert first.state == "CLARIFY"
    reply = await harness.say("Quero falar com uma pessoa, por favor", session, first.conversation_id)
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert "pessoa da equipe" in reply.response.text
    assert reply.response.escalation is not None
    stored = await harness.handoff(session, reply.response.escalation.handoff_id)
    assert stored.handoff.escalation_reason.code.value == "human_requested"
    assert "Which transaction does the customer dispute?" in stored.handoff.open_questions
    assert_schema_valid(stored.handoff)


async def test_7_an_expired_session_pauses_resumes_and_never_duplicates_the_case(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    first = await harness.say(OPENING, session)
    await harness.say("no", session, first.conversation_id)
    pending = await harness.say("sí", session, first.conversation_id)
    assert (pending.state, pending.response.step_up_required) == ("EXECUTE", True)
    harness.clock.advance(timedelta(minutes=20))
    paused = await harness.say("ya hice la verificación", session, first.conversation_id)
    assert paused.state == "AUTH_REQUIRED"
    assert NoticeCode.REAUTHENTICATION_REQUIRED in paused.response.notices
    assert await cases(harness, session) == []
    renewed = harness.session(MX, step_up=True, session_id="ses-mx-renewed")
    resumed = await harness.say("listo", renewed, first.conversation_id)
    assert resumed.state == "CONFIRM_SUMMARY"
    assert resumed.response.text.startswith("Gracias por verificar tu identidad.")
    done = await harness.say("sí", renewed, first.conversation_id)
    assert done.outcome is Outcome.RESOLVED
    again = await harness.say("sí", renewed, first.conversation_id)
    assert again.outcome is not Outcome.ESCALATED
    created = await cases(harness, renewed)
    assert len(created) == 1
    target = SourceRef.model_validate("transactions:TRX-FIXMX-0001")
    assert created[0].idempotency_key == derive_key(first.conversation_id, target, ActionKind.CREATE_DISPUTE_CASE)


async def test_8_another_customers_transaction_id_is_refused_without_disclosure(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    reply = await harness.say("Quiero reclamar la transacción TRX-FIXAR-0001", session)
    assert (reply.state, reply.outcome) == ("REFUSED", Outcome.REFUSED)
    assert "No encontré ese registro" in reply.response.text
    assert "SUPER LA ESQUINA" not in reply.response.text
    assert "15" not in reply.response.text.split("\n\n")[0]
    record = await harness.record(session, reply.turn_id)
    assert record.trust_events_added == (TrustEventKind.CROSS_CUSTOMER_PROBE,)
    assert record.risk_tier is RiskTier.HIGH
    lookup = [call for call in record.tool_calls if call.tool is ToolName.GET_TRANSACTION]
    assert lookup[0].status is ToolCallStatus.NOT_FOUND
    other = harness.session(AR)
    assert await cases(harness, other) == []


async def test_9_a_tool_timeout_after_bounded_retries_escalates_without_false_success(backend: Backend) -> None:
    failures = {ToolName.CREATE_DISPUTE_CASE: ToolFailureMode.TIMEOUT}
    harness = build_harness(backend.uow_factory, backend.session_store, failures=failures)
    session = harness.session(MX, step_up=True)
    first = await harness.say(OPENING, session)
    await harness.say("no", session, first.conversation_id)
    reply = await harness.say("sí", session, first.conversation_id, turn="9b2f0d1e-0000-4000-8000-00000000c009")
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert "registramos" not in reply.response.text
    assert reply.response.action_statuses == ()
    record = await harness.record(session, "9b2f0d1e-0000-4000-8000-00000000c009")
    write = next(call for call in record.tool_calls if call.tool is ToolName.CREATE_DISPUTE_CASE)
    assert (write.status, write.attempts, write.error_code) == (ToolCallStatus.FAILED, 3, "tool_timeout")
    assert reply.response.escalation is not None
    handoff = (await harness.handoff(session, reply.response.escalation.handoff_id)).handoff
    assert handoff.escalation_reason.code.value == "tool_failure"
    assert handoff.actions_taken[0].verification is VerificationStatus.NOT_VERIFIED
    assert await cases(harness, session) == []


async def test_10_pt_br_a_partial_write_is_caught_by_verification(backend: Backend) -> None:
    failures = {ToolName.CREATE_DISPUTE_CASE: ToolFailureMode.PARTIAL_WRITE}
    harness = build_harness(backend.uow_factory, backend.session_store, failures=failures)
    session = harness.session(PT, step_up=True)
    first = await harness.say("Não reconheço uma compra de 88 pesos na PADARIA BOA", session)
    await harness.say("não", session, first.conversation_id)
    reply = await harness.say("sim", session, first.conversation_id, turn="9b2f0d1e-0000-4000-8000-00000000c010")
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert "registramos" not in reply.response.text
    record = await harness.record(session, "9b2f0d1e-0000-4000-8000-00000000c010")
    write = next(call for call in record.tool_calls if call.tool is ToolName.CREATE_DISPUTE_CASE)
    assert write.verification is not None
    assert write.verification.verified is False
    assert reply.response.escalation is not None
    handoff = (await harness.handoff(session, reply.response.escalation.handoff_id)).handoff
    assert handoff.escalation_reason.code.value == "verification_mismatch"
    assert handoff.actions_taken[0].verification is VerificationStatus.MISMATCH


async def test_11_injection_text_in_a_merchant_name_is_only_data(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX, step_up=True)
    first = await harness.say("No reconozco un cargo de 730 pesos del 14 de junio", session)
    assert first.state == "OFFER_PROTECTIVE_BLOCK"
    summary = await harness.say("no", session, first.conversation_id)
    assert INJECTION_MERCHANT[:40] in summary.response.text
    record = await harness.record(session, summary.turn_id)
    assert "record_text_injection_flagged" in record.safety_interventions
    assert record.trust_events_added == ()
    assert record.risk_tier is RiskTier.LOW
    assert all(call.tool not in {ToolName.CREATE_DISPUTE_CASE, ToolName.BLOCK_CARD} for call in record.tool_calls)
    assert record.grounding.violations == ()
    done = await harness.say("sí", session, first.conversation_id)
    assert done.outcome is Outcome.RESOLVED
    assert [case.disputed_amount.amount for case in await cases(harness, session)] == [730]


async def test_19_a_replayed_turn_returns_the_same_result_without_a_second_write(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX, step_up=True)
    first = await harness.say(OPENING, session)
    await harness.say("no", session, first.conversation_id)
    turn = "9b2f0d1e-0000-4000-8000-00000000c019"
    done = await harness.say("sí", session, first.conversation_id, turn=turn)
    replay = await harness.say("sí", session, first.conversation_id, turn=turn)
    assert replay.replayed is True
    assert (replay.state, replay.outcome, replay.response) == (done.state, done.outcome, done.response)
    assert len(await cases(harness, session)) == 1
