"""Credit scenarios 24 to 27 with language variants: catalog answers, an intake for an indicatively eligible profile,
missing income, and a borderline estimate, on the in-memory adapters and PostgreSQL."""

from decimal import Decimal

from bank_agent.domain.credit import ApplicationStatus
from bank_agent.domain.eligibility import EligibilityOutcome, ReviewReason
from bank_agent.domain.identifiers import ApplicationId
from bank_agent.domain.workflow import Outcome, WorkflowRef
from bank_agent.policy.lexicon import approval_terms
from bank_agent_scenarios import CO, MX, PT, PT2
from bank_agent_workflow_support import Backend, assert_no_transcript, assert_schema_valid
from bank_agent_workflows import build_harness

CREDIT = WorkflowRef(id="credit", version=1)


async def test_24_es_co_product_information_with_the_disclaimer_and_no_eligibility(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(CO)
    reply = await harness.say("¿Qué condiciones tiene el préstamo personal?", session)
    assert (reply.state, reply.outcome) == ("PRODUCT_INFO", Outcome.RESOLVED)
    text = reply.response.text
    assert "préstamo personal: montos de 2.000.000,00 COP a 80.000.000,00 COP" in text
    assert "plazos de 6 a 72 meses; tasa anual de 15 % a 27 %" in text
    cited = [str(c.clause) for c in reply.response.citations]
    assert {"CRE-ALL-1@1", "CRE-ALL-2@1", "CRE-CO-1@1"} <= set(cited)
    assert reply.response.eligibility is None
    assert [p.product_code for p in reply.response.credit_products] == ["CO-PL-STANDARD"]
    assert approval_terms(text) == ()
    record = await harness.record(session, reply.turn_id)
    assert record.workflow == CREDIT
    assert (record.risk_estimates, record.eligibility_assessments) == ((), ())
    assert record.grounding.violations == ()


async def test_24b_pt_br_the_catalog_list_marks_mortgages_information_only(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT)
    reply = await harness.say("Quais produtos de crédito vocês têm?", session)
    assert (reply.state, reply.outcome) == ("PRODUCT_INFO", Outcome.RESOLVED)
    assert (
        "financiamento imobiliário: de 500.000,00 MXN a 10.000.000,00 MXN (somente informação)" in reply.response.text
    )
    assert len(reply.response.credit_products) == 3
    assert "CRE-ALL-1@1" in [str(c.clause) for c in reply.response.citations]


async def test_25_pt_br_complete_profile_is_indicative_then_an_intake_is_submitted_and_verified(
    backend: Backend,
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT, step_up=True)
    text = "Sou elegível para um cartão de crédito com limite de 30 mil pesos?"
    explained = await harness.say(text, session)
    assert (explained.state, explained.outcome) == ("EXPLAIN_ELIGIBILITY", Outcome.RESOLVED)
    body = explained.response.text
    assert "o seu perfil atende de forma indicativa" in body
    assert "Motivos, com a regra que os sustenta:" in body
    assert "É uma orientação indicativa" in body or "orientação indicativa" in body
    assert "não é uma oferta" in body.lower() or "Não é uma oferta" in body
    view = explained.response.eligibility
    assert view is not None
    assert view.outcome is EligibilityOutcome.INDICATIVELY_ELIGIBLE
    assert approval_terms(body) == ()
    record = await harness.record(session, explained.turn_id)
    assert [a.outcome for a in record.eligibility_assessments] == [EligibilityOutcome.INDICATIVELY_ELIGIBLE]
    assert [str(e.model) for e in record.risk_estimates] == ["risk_estimator:score_band@1"]
    assert "get_my_credit_profile" in [call.tool.value for call in record.tool_calls]
    confirm = await harness.say("sim", session, explained.conversation_id)
    assert confirm.state == "CONFIRM_INTAKE"
    assert "nenhuma decisão é tomada" in confirm.response.text
    assert confirm.response.credit_intake_confirmation is not None
    done = await harness.say("sim", session, explained.conversation_id)
    assert (done.state, done.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert "registramos a sua solicitação" in done.response.text
    assert done.response.action_statuses[0].status.value == "verified"
    evidence = done.response.action_statuses[0].evidence
    assert evidence is not None
    async with harness.uow_factory(session.access_context()) as uow:
        intake = await uow.credit_applications.get(ApplicationId(evidence.key))
    assert intake is not None
    assert intake.status is ApplicationStatus.SUBMITTED
    assert intake.requested_amount.amount == Decimal("30000")
    record = await harness.record(session, done.turn_id)
    submit = next(call for call in record.tool_calls if call.tool.value == "submit_credit_application")
    assert submit.verification is not None
    assert submit.verification.verified


async def test_26_es_mx_no_income_gives_insufficient_data_and_a_credit_review_handoff(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    text = "Quiero saber si califico para un préstamo personal de 50 mil pesos a 24 meses"
    explained = await harness.say(text, session)
    assert (explained.state, explained.outcome) == ("EXPLAIN_ELIGIBILITY", Outcome.IN_PROGRESS)
    assert "Nos falta información para darte una orientación." in explained.response.text
    assert "Tu ingreso mensual" in explained.response.text
    assert "persona del equipo de crédito revise tu caso" in explained.response.text
    view = explained.response.eligibility
    assert view is not None
    assert view.outcome is EligibilityOutcome.INSUFFICIENT_DATA
    handed = await harness.say("sí, que lo revise una persona", session, explained.conversation_id)
    assert (handed.state, handed.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert handed.response.escalation is not None
    handoff = (await harness.handoff(session, handed.response.escalation.handoff_id)).handoff
    assert_schema_valid(handoff)
    assert_no_transcript(handoff, text)
    assert handoff.escalation_reason.code.value == "credit_review_required"
    review = handoff.credit_review
    assert review is not None
    assert review.eligibility_outcome is EligibilityOutcome.INSUFFICIENT_DATA
    assert "monthly_income" in review.missing_facts
    assert ReviewReason.MISSING_INCOME in review.review_reasons
    assert review.risk is not None


async def test_26b_es_mx_a_declared_income_is_assessed_again(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    first = await harness.say("Quiero saber si califico para un préstamo personal de 50 mil pesos a 24 meses", session)
    assert first.response.eligibility is not None
    again = await harness.say("Gano 40 mil pesos al mes", session, first.conversation_id)
    assert again.state == "EXPLAIN_ELIGIBILITY"
    assert again.response.eligibility is not None
    assert again.response.eligibility.outcome is EligibilityOutcome.INDICATIVELY_ELIGIBLE
    assert "40.000" not in again.response.text
    assert "40,000" not in again.response.text


async def test_27_pt_br_borderline_interval_needs_review_with_separate_record_entries(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT2)
    text = "Posso pedir um empréstimo pessoal de 20 milhões de pesos em 36 meses?"
    explained = await harness.say(text, session)
    assert (explained.state, explained.outcome) == ("EXPLAIN_ELIGIBILITY", Outcome.IN_PROGRESS)
    assert "O seu caso precisa da análise de uma pessoa da equipe de crédito." in explained.response.text
    assert "perto de um limite" in explained.response.text
    record = await harness.record(session, explained.turn_id)
    assert len(record.risk_estimates) == 1
    assert len(record.eligibility_assessments) == 1
    assessment = record.eligibility_assessments[0]
    assert assessment.outcome is EligibilityOutcome.REVIEW_REQUIRED
    assert ReviewReason.BORDERLINE_RISK_INTERVAL in assessment.review_reasons
    assert str(assessment.service).startswith("eligibility:synthetic@")
    assert record.risk_estimates[0].estimate_id not in {r.rule_id for r in assessment.rules}
    probability = str(record.risk_estimates[0].probability)
    assert probability not in explained.response.text
    handed = await harness.say("sim", session, explained.conversation_id)
    assert handed.state == "ESCALATED"
    assert handed.response.escalation is not None
    handoff = (await harness.handoff(session, handed.response.escalation.handoff_id)).handoff
    assert handoff.escalation_reason.code.value == "credit_review_required"
    assert handoff.credit_review is not None
    assert handoff.credit_review.risk is not None
    assert "ESC-ALL-4@1" in [str(ref) for ref in handoff.policy_basis]
