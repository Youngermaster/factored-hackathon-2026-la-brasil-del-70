"""Routing and language regressions from the production QA pass of 2026-10-05, end to end in es and pt: the
request reaches its workflow (or the clause-backed abstention) instead of the generic "saldos o tarjetas" question,
and a conversation keeps its language. Finding ids are in the test names."""

import pytest

from bank_agent.domain.conversation import TurnResult
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import MX, PT
from bank_agent_workflow_support import Backend
from bank_agent_workflows import build_harness

CLARIFY = "common.clarify_workflow"


def _clauses(reply: TurnResult) -> list[str]:
    return [str(c.clause) for c in reply.response.citations]


@pytest.mark.parametrize(("customer", "text"), [(MX, "Quiero un crédito"), (PT, "Quero um crédito")])
async def test_cre01_a_generic_credit_request_reaches_the_credit_workflow(
    backend: Backend, customer: str, text: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    reply = await harness.say(text, harness.session(customer))
    assert reply.response.template_id != CLARIFY
    assert reply.workflow is not None
    assert reply.workflow.id == "credit"


@pytest.mark.parametrize(
    ("customer", "text"), [(MX, "¿Cuál es mi puntaje de crédito?"), (PT, "Qual é a minha pontuação de crédito?")]
)
async def test_cre08_a_score_question_is_abstained_without_reading_the_profile(
    backend: Backend, customer: str, text: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(customer)
    reply = await harness.say(text, session)
    assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
    assert "ELG-ALL-2@1" in _clauses(reply)
    record = await harness.record(session, reply.turn_id)
    assert all("credit_profile" not in str(call.tool) for call in record.tool_calls)


@pytest.mark.parametrize(
    ("customer", "text"),
    [
        (MX, "Quiero retirar mi solicitud de crédito"),
        (PT, "Quero cancelar a minha solicitação de crédito"),
        (MX, "Quiero que me suban el límite de la tarjeta"),
        (PT, "Quero elevar o meu limite do cartão"),
    ],
)
async def test_cre12_cre15_withdrawals_and_limit_increases_are_abstained_in_credit(
    backend: Backend, customer: str, text: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(customer)
    reply = await harness.say(text, session)
    assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
    assert "CRE-ALL-3@1" in _clauses(reply)
    record = await harness.record(session, reply.turn_id)
    assert record.tool_calls == ()


@pytest.mark.parametrize(
    ("customer", "text", "workflow"),
    [
        (MX, "¿Mi transferencia sí se hizo?", "account_inquiry"),
        (PT, "Cadê minha transferência? Mandei um pix ontem e não caiu", "account_inquiry"),
        (MX, "Hola, ¿cómo va mi reclamo?", "dispute"),
        (PT, "Oi! Queria saber como está a minha contestação", "dispute"),
    ],
)
async def test_acc06_dsp03_payment_and_dispute_status_phrasings_reach_their_workflow(
    backend: Backend, customer: str, text: str, workflow: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    reply = await harness.say(text, harness.session(customer, step_up=True))
    assert reply.response.template_id not in {CLARIFY, "common.greeting"}
    assert reply.workflow is not None
    assert reply.workflow.id == workflow


async def test_cre05_a_clear_spanish_eligibility_question_is_answered_in_spanish(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    reply = await harness.say("¿Califico para un préstamo personal de 50 mil pesos a 12 meses?", harness.session(MX))
    assert reply.response.template_id != "common.language_question"
    assert reply.response.language is Language.ES


async def test_cre04_a_portuguese_conversation_stays_portuguese_on_por_que(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT)
    first = await harness.say("Quero saber se sou elegível para um empréstimo pessoal", session)
    assert first.response.language is Language.PT
    follow_up = await harness.say("Por que precisa de análise? O que está pendente?", session, first.conversation_id)
    assert follow_up.response.language is Language.PT


async def test_acc05_a_spanish_conversation_stays_spanish_on_la_mas_reciente(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    first = await harness.say("¿Cuál es el estado de mi última transferencia?", session)
    assert first.response.language is Language.ES
    follow_up = await harness.say("la más reciente", session, first.conversation_id)
    assert follow_up.response.language is Language.ES
