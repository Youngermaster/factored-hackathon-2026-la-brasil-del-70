"""Follow-ups to an answer in a state that holds context continue the same workflow (QA findings ACC-01, ACC-02,
CRD-03): a message that only names a product, a card, or a period gets that answer instead of the generic workflow
question or an off-topic abstention. Messages that name nothing, or another workflow, keep their routing."""

import pytest

from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import MX, PT
from bank_agent_workflow_support import Backend
from bank_agent_workflows import build_harness


@pytest.mark.parametrize(
    ("first", "follow_up"),
    [
        ("¿Cuál es mi saldo?", "¿y nomás en la de ahorro?"),
        ("Qual é o saldo das minhas contas?", "e da poupança só?"),
    ],
)
async def test_a_product_follow_up_after_balances_answers_that_product_only(
    backend: Backend, first: str, follow_up: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT if first.startswith("Qual") else MX)
    shown = await harness.say(first, session)
    assert (shown.state, shown.outcome) == ("BALANCES", Outcome.RESOLVED)
    reply = await harness.say(follow_up, session, shown.conversation_id)
    assert (reply.state, reply.outcome) == ("BALANCES", Outcome.RESOLVED)
    assert reply.response.balances
    assert {b.product_type.value for b in reply.response.balances} == {"savings_account"}
    record = await harness.record(session, reply.turn_id)
    assert "router:context_follow_up@1" in [str(model) for model in record.models]


@pytest.mark.parametrize(
    ("first", "follow_up"),
    [
        ("Quiero el resumen de mi tarjeta de crédito del mes pasado", "y ahora el de abril"),
        ("Quero o extrato do meu cartão de crédito do mês passado", "tá, então só de abril"),
    ],
)
async def test_a_period_follow_up_after_a_statement_stays_in_the_statement_inquiry(
    backend: Backend, first: str, follow_up: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT if first.startswith("Quero") else MX)
    shown = await harness.say(first, session)
    assert shown.state == "STATEMENT_SUMMARY"
    reply = await harness.say(follow_up, session, shown.conversation_id)
    assert reply.response.text != shown.response.text
    assert reply.state in {"STATEMENT_SUMMARY", "CLARIFY"}
    assert reply.workflow.id == "account_inquiry"
    assert reply.response.template_id not in {"common.off_topic", "common.clarify_workflow"}


@pytest.mark.parametrize(
    ("first", "follow_up", "last4"),
    [
        ("Situação do meu cartão de crédito", "e o de débito?", "1357"),
        ("Estado de mi tarjeta de crédito", "¿y la terminada en 1357?", "1357"),
        ("Estado de mi tarjeta de débito", "¿y la de crédito?", "2468"),
    ],
)
async def test_a_card_follow_up_after_a_status_answer_shows_that_card(
    backend: Backend, first: str, follow_up: str, last4: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT)
    shown = await harness.say(first, session)
    assert shown.state == "CARD_STATUS"
    reply = await harness.say(follow_up, session, shown.conversation_id)
    assert (reply.state, reply.outcome) == ("CARD_STATUS", Outcome.RESOLVED)
    assert [card.masked_number.last4 for card in reply.response.card_status] == [last4]
    assert reply.response.escalation is None


async def test_an_unrelated_message_after_balances_is_still_off_topic(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    shown = await harness.say("¿Cuál es mi saldo?", session)
    reply = await harness.say("¿Quién es mejor, CR7 o Messi?", session, shown.conversation_id)
    assert reply.outcome is Outcome.ABSTAINED
    assert reply.response.balances == ()
