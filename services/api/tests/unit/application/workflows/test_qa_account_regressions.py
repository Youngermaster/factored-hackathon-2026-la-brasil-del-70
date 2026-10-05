"""Account inquiry and dispute copy regressions from the 2026-10-05 production QA pass (ACC-03, 08, 10, 11 and
DSP-10), in es and pt, driven through the engine on the in-memory adapters with the deterministic fallback."""

from datetime import UTC, datetime

import pytest

from bank_agent.adapters.persistence.memory.sessions import InMemorySessionStore
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory
from bank_agent.application.workflows.account_inquiry.answers import contested
from bank_agent.domain.money import Currency
from bank_agent.domain.transaction import TransactionType
from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import CO, MX, PT, scenario_data, txn
from bank_agent_workflow_support import Backend
from bank_agent_workflows import Harness, build_harness

OCTOBER = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)


@pytest.fixture
def backend() -> Backend:
    """The scenario data plus records without a payee or merchant: a transfer and a cash withdrawal."""
    data = scenario_data()
    data.transactions += [
        txn("TRX-FIXPT-0199", PT, "PRD-FIXPT-SAV", "700.00", Currency.MXN, "2026-06-16", "",
            kind=TransactionType.TRANSFER),
        txn("TRX-FIXCO-0199", CO, "PRD-FIXCO-CRED", "300000.00", Currency.COP, "2026-06-14", "",
            kind=TransactionType.WITHDRAWAL),
    ]  # fmt: skip
    store = InMemoryStore()
    store.seed(customers=data.customers, products=data.products, transactions=data.transactions, cases=data.cases,
               credit_profiles=data.credit_profiles)  # fmt: skip
    return Backend(InMemoryUnitOfWorkFactory(store), InMemorySessionStore())


def harness_of(backend: Backend) -> Harness:
    return build_harness(backend.uow_factory, backend.session_store)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("esse saldo da poupança tá errado, era pra ter mais dinheiro aí", True),
        ("o saldo tá errado", True),
        ("no me cierra ese número", True),
        ("Che, ¿me pasás el saldo de la caja de ahorro?", False),
        ("tá bom, obrigado", False),
    ],
)
def test_colloquial_contested_balances_are_recognized(text: str, expected: bool) -> None:
    assert contested(text) is expected


async def test_a_colloquial_portuguese_contested_balance_escalates(backend: Backend) -> None:
    harness = harness_of(backend)
    session = harness.session(PT)
    first = await harness.say("Qual é o saldo da minha conta poupança?", session)
    assert first.state == "BALANCES"
    reply = await harness.say("esse saldo da poupança tá errado, era pra ter mais dinheiro aí", session,
                              first.conversation_id)  # fmt: skip
    assert reply.outcome is Outcome.ESCALATED


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Quiero el estado de cuenta de mi tarjeta de crédito del mes pasado",
         "del 1 de mayo de 2026 al 31 de mayo de 2026, con datos al 17 de junio de 2026"),
        ("Quero o extrato do meu cartão de crédito do mês passado",
         "de 1 de maio de 2026 a 31 de maio de 2026, com dados de 17 de junho de 2026"),
    ],
)  # fmt: skip
async def test_relative_statement_periods_count_from_the_data_cut_not_the_wall_clock(
    backend: Backend, text: str, expected: str
) -> None:
    harness = harness_of(backend)
    harness.clock.set(OCTOBER)
    session = harness.session(MX)
    reply = await harness.say(text, session)
    assert (reply.state, reply.outcome) == ("STATEMENT_SUMMARY", Outcome.RESOLVED)
    assert expected in reply.response.text
    assert reply.response.statement is not None
    assert reply.response.statement.transaction_count == 4


async def test_portuguese_statement_agrees_in_gender_with_the_product(backend: Backend) -> None:
    harness = harness_of(backend)
    reply = await harness.say("Quero o extrato da minha conta poupança de junho", harness.session(PT))
    assert reply.state == "STATEMENT_SUMMARY"
    assert "da sua conta poupança" in reply.response.text
    assert "do seu conta" not in reply.response.text
    card = await harness.say("Quero o extrato do meu cartão de crédito de maio", harness.session(MX))
    assert "do seu cartão de crédito" in card.response.text


async def test_a_payment_without_a_payee_is_never_shown_with_a_dash(backend: Backend) -> None:
    harness = harness_of(backend)
    session = harness.session(PT)
    reply = await harness.say("Qual a situação da minha transferência de 700 pesos?", session)
    assert reply.state == "PAYMENT_STATUS"
    assert "para -" not in reply.response.text
    assert " -," not in reply.response.text
    assert reply.response.template_id == "account.payment_status_no_payee"
    record = await harness.record(session, reply.turn_id)
    assert record.grounding.violations == ()


async def test_a_dispute_summary_without_a_merchant_leaves_the_merchant_out(backend: Backend) -> None:
    harness = harness_of(backend)
    session = harness.session(CO, step_up=True)
    first = await harness.say("No reconozco un retiro de 300000 pesos del 14 de junio", session)
    summary = first
    if first.state == "OFFER_PROTECTIVE_BLOCK":
        assert "no reconoces este cargo" in first.response.text
        summary = await harness.say("no", session, first.conversation_id)
    assert summary.state == "CONFIRM_SUMMARY"
    assert " en - " not in summary.response.text
    assert "la compra" not in summary.response.text
    assert summary.response.confirmation is not None
    assert summary.response.confirmation.merchant_display is None
