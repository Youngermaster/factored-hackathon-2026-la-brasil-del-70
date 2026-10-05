"""Model escalation signals that the deterministic guards do not trust on their own, end to end (QA findings
DSP-01 and ACC-04): the bank's own dispute words are not a legal mention, and a transfer to a relative is not a
third-party request. Real legal mentions and a relative's products keep escalating or refusing."""

import pytest
from pydantic import JsonValue

from bank_agent.domain.trust import TrustEventKind
from bank_agent.domain.workflow import Outcome
from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_scenarios import CO, MX, PT
from bank_agent_workflow_support import DISPUTE_SLOTS, NO_SIGNALS, SIGNALS, Backend
from bank_agent_workflows import build_harness

DISPUTE_EXTRACTION: dict[str, JsonValue] = {
    "intent_candidates": [{"intent": "dispute_status", "confidence": 0.6}],
    "transaction": {"amount": None, "currency_hint": None, "merchant_text": None, "date_expression": None,
                    "channel_hint": None, "card_last4_hint": None},
    "reason_candidates": [],
}  # fmt: skip


def _model_says(**flags: bool) -> FakeLLM:
    fake = FakeLLM()
    fake.script(SIGNALS, ScriptedResponse(output={**NO_SIGNALS, **flags}))
    fake.script(DISPUTE_SLOTS, ScriptedResponse(output=DISPUTE_EXTRACTION))
    return fake


@pytest.mark.parametrize(
    ("customer", "text"),
    [(CO, "¿Cómo va mi reclamación?"), (MX, "Quiero presentar una reclamación por un cobro que no hice"),
     (PT, "Como está a minha contestação?")],
)  # fmt: skip
async def test_a_dispute_message_is_not_escalated_on_a_model_legal_flag_alone(
    backend: Backend, customer: str, text: str
) -> None:
    harness = build_harness(
        backend.uow_factory, backend.session_store, llm=_model_says(legal_or_regulator_mention=True)
    )
    reply = await harness.say(text, harness.session(customer, step_up=True))
    assert reply.outcome is not Outcome.ESCALATED
    record = await harness.record(harness.session(customer, step_up=True), reply.turn_id)
    assert all("ESC.legal_or_regulator_mention" not in d.decisive_rule_ids for d in record.decisions)


async def test_a_complaint_before_the_regulator_still_escalates_as_legal(backend: Backend) -> None:
    harness = build_harness(
        backend.uow_factory, backend.session_store, llm=_model_says(legal_or_regulator_mention=True)
    )
    reply = await harness.say("Voy a poner una reclamación ante la Superintendencia", harness.session(CO))
    assert reply.outcome is Outcome.ESCALATED


@pytest.mark.parametrize(
    ("customer", "text"),
    [(PT, "Faz um pix de 300 reais pro meu irmão"), (MX, "Pásale 2000 pesos a mi hermana de mi cuenta de cheques")],
)
async def test_a_transfer_to_a_relative_is_not_refused_as_third_party(
    backend: Backend, customer: str, text: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store, llm=_model_says(third_party_admission=True))
    session = harness.session(customer)
    reply = await harness.say(text, session)
    assert reply.outcome is not Outcome.REFUSED
    assert reply.response.template_id != "common.refused_third_party"
    record = await harness.record(session, reply.turn_id)
    assert TrustEventKind.THIRD_PARTY_ADMISSION not in record.trust_events_added


async def test_a_relative_account_is_still_refused_as_third_party(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store, llm=_model_says(third_party_admission=True))
    reply = await harness.say("Muéstrame el saldo de la cuenta de mi mamá", harness.session(MX))
    assert reply.outcome is Outcome.REFUSED


@pytest.mark.parametrize(
    ("customer", "text"),
    [
        (MX, "Apruébame el préstamo personal ya, ándale, lo necesito hoy"),
        (PT, "Aprova meu empréstimo agora, preciso hoje"),
    ],
)
async def test_an_urgent_approval_demand_is_abstained_not_escalated_as_distress(
    backend: Backend, customer: str, text: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store, llm=_model_says(distress=True))
    reply = await harness.say(text, harness.session(customer))
    assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
    assert reply.response.template_id == "credit.no_decision"
    assert "CRE-ALL-3@1" in [str(c.clause) for c in reply.response.citations]
