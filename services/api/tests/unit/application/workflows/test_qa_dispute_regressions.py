"""Dispute regressions from the 2026-10-05 production QA pass (DSP-02, 06, 07, 11, 12, 14, 16), in es and pt,
driven through the engine on the in-memory adapters with a scripted model."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.workflow import Outcome
from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_scenarios import AR, CO, MX, PT
from bank_agent_workflow_support import (
    DISPUTE_SLOTS,
    NO_SIGNALS,
    SIGNALS,
    Backend,
    assert_no_transcript,
    assert_schema_valid,
    memory_backend,
)
from bank_agent_workflows import Harness, build_harness


@pytest.fixture
async def backend(request: pytest.FixtureRequest) -> AsyncIterator[Backend]:
    async for value in memory_backend(request):
        yield value


def slots(reasons: list[str], **transaction: Any) -> dict[str, Any]:
    txn = None
    if transaction:
        txn = {"amount": None, "currency_hint": None, "merchant_text": None, "date_expression": None,
               "channel_hint": None, "card_last4_hint": None, **transaction}  # fmt: skip
    return {"intent_candidates": [{"intent": "dispute_new", "confidence": 0.9}], "transaction": txn,
            "reason_candidates": reasons}  # fmt: skip


def harness_with(backend: Backend, *extractions: dict[str, Any]) -> Harness:
    if not extractions:
        return build_harness(backend.uow_factory, backend.session_store)
    fake = FakeLLM()
    fake.script(SIGNALS, *[ScriptedResponse(output=NO_SIGNALS) for _ in range(8)])
    fake.script(DISPUTE_SLOTS, *[ScriptedResponse(output=e) for e in extractions])
    return build_harness(backend.uow_factory, backend.session_store, llm=fake)


@pytest.mark.parametrize(
    ("customer", "first", "second", "amount"),
    [
        (MX, "No reconozco un cargo en mi tarjeta", "Fue el 15 de junio, como 1250 pesos", "1250"),
        (PT, "Não reconheço uma cobrança no meu cartão", "Foi no dia 13 de junho, uns 88 pesos", "88"),
    ],
)
async def test_multi_turn_intake_keeps_the_reason_when_the_follow_up_has_only_details(
    backend: Backend, customer: str, first: str, second: str, amount: str
) -> None:
    harness = harness_with(backend, slots(["unrecognized"]), slots(["other"], amount=amount))
    session = harness.session(customer, step_up=True)
    opened = await harness.say(first, session)
    assert opened.state == "CLARIFY"
    details = await harness.say(second, session, opened.conversation_id)
    assert details.outcome is not Outcome.ESCALATED
    assert details.state in ("OFFER_PROTECTIVE_BLOCK", "CONFIRM_SUMMARY")
    if details.state == "OFFER_PROTECTIVE_BLOCK":
        details = await harness.say("no" if customer == MX else "não", session, opened.conversation_id)
    assert details.response.confirmation is not None
    assert details.response.confirmation.reason is DisputeReason.UNRECOGNIZED


async def test_a_newly_stated_specific_reason_still_replaces_the_first_one(backend: Backend) -> None:
    harness = harness_with(backend, slots(["unrecognized"]), slots(["duplicate"], amount="1250"))
    session = harness.session(MX, step_up=True)
    opened = await harness.say("No reconozco un cargo en mi tarjeta", session)
    details = await harness.say("en realidad me cobraron dos veces, 1250 pesos el 15 de junio", session,
                                opened.conversation_id)  # fmt: skip
    assert details.outcome is not Outcome.ESCALATED
    assert details.response.confirmation is not None
    assert details.response.confirmation.reason is DisputeReason.DUPLICATE


async def test_unsupported_reason_handoff_carries_the_reason_open_question(backend: Backend) -> None:
    text = "Tengo un cargo indebido de 300 pesos de CAFE LUNA del 10 de junio, el servicio fue pésimo"
    extraction = slots(["other"], amount="300", merchant_text="CAFE LUNA", date_expression="el 10 de junio")
    harness = harness_with(backend, extraction)
    session = harness.session(MX, step_up=True)
    reply = await harness.say(text, session)
    assert reply.outcome is Outcome.ESCALATED
    assert reply.response.escalation is not None
    handoff = (await harness.handoff(session, reply.response.escalation.handoff_id)).handoff
    assert any("DSP-ALL-3" in question for question in handoff.open_questions)
    assert_schema_valid(handoff)
    assert_no_transcript(handoff, text)


@pytest.mark.parametrize(
    ("text", "yes", "case_word"),
    [
        ("No recibí el pedido de LIBRERIA BOGOTA, el cargo de 42000 pesos del 20 de mayo", "sí", "abierto"),
        ("Não recebi o pedido da LIBRERIA BOGOTA, a cobrança de 42000 pesos de 20 de maio", "sim", "aberto"),
    ],
)
async def test_duplicate_dispute_abstention_names_the_existing_case_and_status(
    backend: Backend, text: str, yes: str, case_word: str
) -> None:
    harness = harness_with(backend)
    session = harness.session(CO, step_up=True)
    reply = await harness.say(text, session)
    assert reply.outcome is Outcome.ABSTAINED
    assert "case-fixco000001-0001" in reply.response.text
    assert case_word in reply.response.text
    record = await harness.record(session, reply.turn_id)
    assert any(str(ref).startswith("DSP-ALL-4") for ref in record.clause_refs)
    assert record.grounding.violations == ()
    follow = await harness.say(yes, session, reply.conversation_id)
    assert follow.outcome is Outcome.ESCALATED


@pytest.mark.parametrize(
    ("customer", "text", "clause"),
    [
        (MX, "No reconozco un cargo del 10 de enero de 2026", "DSP-MX-1"),
        (AR, "No reconozco un cargo del 2 de abril de 2026", "DSP-AR-1"),
        (PT, "Não reconheço uma cobrança de 10 de janeiro de 2026", "DSP-MX-1"),
    ],
)
async def test_a_charge_before_the_dispute_window_gets_the_window_abstention(
    backend: Backend, customer: str, text: str, clause: str
) -> None:
    harness = harness_with(backend)
    session = harness.session(customer, step_up=True)
    reply = await harness.say(text, session)
    assert reply.outcome is Outcome.ABSTAINED
    assert reply.response.template_id == "dispute.denied"
    record = await harness.record(session, reply.turn_id)
    assert any(str(ref).startswith(clause) for ref in record.clause_refs)


async def test_a_single_candidate_is_offered_as_a_yes_or_no_question(backend: Backend) -> None:
    harness = harness_with(backend)
    session = harness.session(CO, step_up=True)
    reply = await harness.say("No reconozco un cargo de junio", session)
    assert reply.state == "CLARIFY"
    assert reply.response.template_id == "dispute.clarify_one"
    assert "varias" not in reply.response.text
    chosen = await harness.say("sí", session, reply.conversation_id)
    assert chosen.state in ("OFFER_PROTECTIVE_BLOCK", "CONFIRM_SUMMARY")


async def test_a_month_only_description_offers_that_months_transactions(backend: Backend) -> None:
    harness = harness_with(backend)
    session = harness.session(AR, step_up=True)
    reply = await harness.say("No reconozco un cargo de junio", session)
    assert reply.state == "CLARIFY"
    assert reply.response.template_id == "dispute.clarify_options"
    assert "SUPER LA ESQUINA" in reply.response.text


@pytest.mark.parametrize(
    ("customer", "text", "no", "question", "expected"),
    [
        (MX, "No reconozco el cargo de 1250 pesos en FIXTURE MARKET del 15 de junio", "no",
         "¿Me garantizan que me devuelven el dinero?", "no garantiza un reembolso"),
        (PT, "Não reconheço a cobrança de 88 pesos na PADARIA BOA de 13 de junho", "não",
         "Vocês garantem que vou ter o dinheiro de volta?", "não garante reembolso"),
    ],
)  # fmt: skip
async def test_a_refund_guarantee_question_at_the_summary_gets_an_answer(
    backend: Backend, customer: str, text: str, no: str, question: str, expected: str
) -> None:
    harness = harness_with(backend)
    session = harness.session(customer, step_up=True)
    first = await harness.say(text, session)
    summary = first
    if first.state == "OFFER_PROTECTIVE_BLOCK":
        summary = await harness.say(no, session, first.conversation_id)
    assert summary.state == "CONFIRM_SUMMARY"
    answer = await harness.say(question, session, first.conversation_id)
    assert answer.state == "CONFIRM_SUMMARY"
    assert expected in answer.response.text
    record = await harness.record(session, answer.turn_id)
    assert any(str(ref).startswith("INF-ALL-1") for ref in record.clause_refs)


@pytest.mark.parametrize(
    ("text", "paragraph"),
    [
        ("¿Cómo va mi reclamación?", "El equipo de revisión analiza la transacción"),
        ("Qual é a situação da minha contestação?", "A equipe de análise examina a transação"),
    ],
)
async def test_dispute_status_cites_the_after_filing_clause_without_appending_it(
    backend: Backend, text: str, paragraph: str
) -> None:
    harness = harness_with(backend)
    session = harness.session(CO)
    reply = await harness.say(text, session)
    assert reply.state == "RESOLVED"
    assert "case-fixco000001-0001" in reply.response.text
    assert paragraph not in reply.response.text
    assert "INF-ALL-1@1" in [str(c.clause) for c in reply.response.citations]
