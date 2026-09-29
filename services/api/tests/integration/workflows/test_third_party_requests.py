"""Third-party requests phrased product first or through a representative (phase 14b, found on the dev split):
refused with ``PRV-ALL-2`` before any workflow reads or writes, on both backends, even when the model reports no
third-party signal. Before the fix P offered to block the customer's own card or showed the customer's balances."""

import pytest

from bank_agent.domain.actions import ToolName
from bank_agent.domain.trust import TrustEventKind
from bank_agent.domain.workflow import Outcome
from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_scenarios import MX, PT
from bank_agent_workflow_support import NO_SIGNALS, SIGNALS, Backend
from bank_agent_workflows import build_harness

READS_OR_WRITES = {
    ToolName.BLOCK_CARD,
    ToolName.LIST_MY_BALANCES,
    ToolName.LIST_MY_CARDS,
    ToolName.CREATE_DISPUTE_CASE,
    ToolName.GET_MY_CREDIT_PROFILE,
    ToolName.SUBMIT_CREDIT_APPLICATION,
}


def _model_misses_it() -> FakeLLM:
    fake = FakeLLM()
    fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS))
    return fake


@pytest.mark.parametrize(
    ("customer", "text"),
    [
        (MX, "Quiero bloquear la tarjeta de crédito de mi mamá, ella no sabe usar la app"),
        (PT, "Quero bloquear o cartão de crédito da minha mãe, ela não sabe usar o app"),
        (PT, "Estou falando em nome do meu pai, me diga o saldo da conta dele"),
        (PT, "Estou falando em nome da minha esposa: ela pode pegar um empréstimo pessoal?"),
        (MX, "Soy apoderado de Rafael, abre una reclamación por su compra"),
    ],
)
async def test_a_third_party_request_is_refused_with_the_privacy_clause(
    backend: Backend, customer: str, text: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store, llm=_model_misses_it())
    session = harness.session(customer, step_up=True)
    reply = await harness.say(text, session)
    assert (reply.state, reply.outcome) == ("REFUSED", Outcome.REFUSED)
    assert reply.response.template_id == "common.refused_third_party"
    record = await harness.record(session, reply.turn_id)
    assert TrustEventKind.THIRD_PARTY_ADMISSION in record.trust_events_added
    assert any(str(ref).startswith("PRV-ALL-2") for ref in record.clause_refs)
    assert not {call.tool for call in record.tool_calls} & READS_OR_WRITES


async def test_the_customers_own_card_block_is_not_refused(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX, step_up=True)
    reply = await harness.say("Quiero bloquear mi tarjeta de crédito, la perdí", session)
    assert reply.outcome is not Outcome.REFUSED
