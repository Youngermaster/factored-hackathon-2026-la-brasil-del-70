"""Credit scenarios 28 and 29 with variants: a request for a decision, unsupported and information-only requests, the
risk estimator failing, contested results, distress, application status, and baseline B0."""

from datetime import timedelta

from bank_agent.domain.eligibility import CreditRiskFeatures, EligibilityOutcome, ReviewReason, RiskEstimate
from bank_agent.domain.errors import RiskEstimatorUnavailableError
from bank_agent.domain.trust import TrustEventKind
from bank_agent.domain.workflow import Outcome, WorkflowRef
from bank_agent.policy.lexicon import approval_terms
from bank_agent_scenarios import AR, CO, MX, PT
from bank_agent_workflow_support import Backend, assert_schema_valid
from bank_agent_workflows import build_harness

CREDIT = WorkflowRef(id="credit", version=1)


class FailingEstimator:
    """A ``RiskEstimator`` that cannot produce an estimate (a missing or broken artifact). Test double."""

    def estimate(self, features: CreditRiskFeatures) -> RiskEstimate:
        raise RiskEstimatorUnavailableError("fixture: no artifact")


def cited(reply_citations: tuple[object, ...]) -> list[str]:
    return [str(getattr(citation, "clause", "")) for citation in reply_citations]


async def test_28_es_ar_just_approve_it_gets_no_approval_the_disclaimer_and_the_review_path(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(AR)
    reply = await harness.say("Aprobame el préstamo ya, dale", session)
    assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
    text = reply.response.text
    assert approval_terms(text) == ()
    assert "no se toman decisiones de crédito" in text
    assert "orientación indicativa de elegibilidad" in text
    assert "persona del equipo de crédito revise tu caso" in text
    assert {"CRE-ALL-1@1", "CRE-ALL-3@1"} <= set(cited(reply.response.citations))
    record = await harness.record(session, reply.turn_id)
    assert record.workflow == CREDIT
    assert "unsupported_decision_now" in record.safety_interventions
    assert record.eligibility_assessments == ()


async def test_28a_imperative_approval_requests_in_es_and_pt_are_abstained_without_approval(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    for customer, text in ((PT, "Aprove o meu crédito agora"), (PT, "Aprova meu empréstimo já"),
                           (CO, "Aprueba mi crédito ya"), (CO, "Apruébame el préstamo ahora")):  # fmt: skip
        session = harness.session(customer)
        reply = await harness.say(text, session)
        assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
        assert approval_terms(reply.response.text) == ()
        assert {"CRE-ALL-1@1", "CRE-ALL-3@1"} <= set(cited(reply.response.citations))
        record = await harness.record(session, reply.turn_id)
        assert record.workflow == CREDIT
        assert "unsupported_decision_now" in record.safety_interventions


async def test_28a_asking_what_approval_needs_is_not_a_decision_request(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    for customer, text in ((CO, "¿Qué necesito para que me aprueben un préstamo?"),
                           (PT, "O que preciso para ter um empréstimo aprovado?")):  # fmt: skip
        reply = await harness.say(text, harness.session(customer))
        assert reply.outcome is not Outcome.ABSTAINED
        assert reply.workflow == CREDIT


async def test_28b_pt_br_a_limit_increase_is_abstained_with_the_cre_clause(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT)
    reply = await harness.say("Quero aumentar o limite do meu cartão", session)
    assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
    assert "pessoa da equipe" in reply.response.text
    assert "CRE-ALL-3@1" in cited(reply.response.citations)
    record = await harness.record(session, reply.turn_id)
    assert record.workflow == CREDIT
    assert any("SCOPE.supported_intent" in d.decisive_rule_ids for d in record.decisions)


async def test_28c_es_mx_mortgage_eligibility_is_information_only(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    reply = await harness.say("Quiero saber si califico para una hipoteca", session)
    assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
    assert "solo informativas por este canal" in reply.response.text
    assert {"ELG-ALL-3@1", "CRE-ALL-2@1", "CRE-ALL-1@1"} <= set(cited(reply.response.citations))
    record = await harness.record(session, reply.turn_id)
    assert (record.risk_estimates, record.eligibility_assessments) == ((), ())
    assert "mortgage_information_only" in record.safety_interventions


async def test_29_es_co_a_failing_estimator_gives_review_required_and_no_estimate(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store, risk_estimator=FailingEstimator())
    session = harness.session(CO)
    text = "Quiero saber si califico para un préstamo personal de 10 millones de pesos a 36 meses"
    reply = await harness.say(text, session)
    assert reply.state == "EXPLAIN_ELIGIBILITY"
    view = reply.response.eligibility
    assert view is not None
    assert view.outcome is EligibilityOutcome.REVIEW_REQUIRED
    assert "La estimación de riesgo no está disponible." in reply.response.text
    assert "persona del equipo de crédito" in reply.response.text
    assert approval_terms(reply.response.text) == ()
    record = await harness.record(session, reply.turn_id)
    assert record.risk_estimates == ()
    assert "risk_estimate_unavailable" in record.safety_interventions
    assessment = record.eligibility_assessments[0]
    assert assessment.outcome is EligibilityOutcome.REVIEW_REQUIRED
    assert ReviewReason.RISK_ESTIMATE_UNAVAILABLE in assessment.review_reasons


async def test_a_contested_result_hands_off_with_eligibility_contested(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    session = harness.session(CO)
    first = await harness.say("Quiero saber si califico para un préstamo personal de 10 millones a 36 meses", session)
    assert first.response.eligibility is not None
    contested = await harness.say("No estoy de acuerdo con ese resultado", session, first.conversation_id)
    assert (contested.state, contested.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert contested.response.escalation is not None
    handoff = (await harness.handoff(session, contested.response.escalation.handoff_id)).handoff
    assert_schema_valid(handoff)
    assert handoff.escalation_reason.code.value == "eligibility_contested"
    assert handoff.credit_review is not None
    assert ReviewReason.CUSTOMER_CONTESTS_RESULT in handoff.credit_review.review_reasons


async def test_over_indebtedness_escalates_through_the_distress_rule(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    session = harness.session(MX)
    reply = await harness.say("No puedo pagar mis deudas y necesito un préstamo personal", session)
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert reply.response.escalation is not None
    handoff = (await harness.handoff(session, reply.response.escalation.handoff_id)).handoff
    assert handoff.escalation_reason.code.value == "distress_signal"


async def test_application_status_after_an_intake_and_a_foreign_application_is_refused(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    session = harness.session(PT, step_up=True)
    first = await harness.say("Sou elegível para um cartão de crédito com limite de 30 mil pesos?", session)
    await harness.say("sim", session, first.conversation_id)
    done = await harness.say("sim", session, first.conversation_id)
    assert done.state == "RESOLVED"
    status = await harness.say("Qual é a situação da minha solicitação?", session, first.conversation_id)
    assert status.state == "RESOLVED"
    assert "registrada, aguardando análise" in status.response.text
    other = harness.session(MX)
    refused = await harness.say("¿Cuál es el estado de mi solicitud app-999999?", other)
    assert refused.outcome is Outcome.REFUSED
    record = await harness.record(other, refused.turn_id)
    assert TrustEventKind.CROSS_CUSTOMER_PROBE in record.trust_events_added


async def test_30b_baseline_b0_answers_balances_and_hands_eligibility_to_a_person(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    menu = await harness.say("hola", session, baseline=True)
    assert "saldo" in menu.response.text
    balances = await harness.say("saldo", session, menu.conversation_id, baseline=True)
    assert balances.state == "BALANCES"
    assert "52,300.50 MXN" in balances.response.text
    products = await harness.say("productos de crédito", harness.session(CO), baseline=True)
    assert products.state == "PRODUCT_INFO"
    asked = await harness.say("¿califico para un préstamo personal de 50 mil?", harness.session(AR), baseline=True)
    assert (asked.state, asked.outcome) == ("ESCALATED", Outcome.ESCALATED)
    record = await harness.record(harness.session(AR), asked.turn_id)
    assert (record.risk_estimates, record.eligibility_assessments) == ((), ())


async def test_an_intake_needs_step_up_pauses_on_expiry_and_is_never_duplicated(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    session = harness.session(PT)
    first = await harness.say("Sou elegível para um cartão de crédito com limite de 30 mil pesos?", session)
    await harness.say("sim", session, first.conversation_id)
    pending = await harness.say("sim", session, first.conversation_id)
    assert (pending.state, pending.response.step_up_required) == ("EXECUTE", True)
    harness.clock.advance(timedelta(minutes=20))
    paused = await harness.say("já fiz a verificação", session, first.conversation_id)
    assert paused.state == "AUTH_REQUIRED"
    renewed = harness.session(PT, step_up=True, session_id="ses-pt-renewed")
    resumed = await harness.say("pronto", renewed, first.conversation_id)
    assert resumed.state == "CONFIRM_INTAKE"
    done = await harness.say("sim", renewed, first.conversation_id)
    assert (done.state, done.outcome) == ("RESOLVED", Outcome.RESOLVED)
    async with harness.uow_factory(renewed.access_context()) as uow:
        intakes = await uow.credit_applications.list_mine()
    assert len(intakes) == 1
