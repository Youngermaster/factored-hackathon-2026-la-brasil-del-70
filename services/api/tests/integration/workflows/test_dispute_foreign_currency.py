"""A USD card charge is compared with the auto intake limit at the pack's synthetic rate, not escalated as too large.

Regression for the production finding where an es-CO intake of 261.15 USD escalated citing the 2,000,000.00 COP
limit because the rule refused to compare currencies.
"""

from bank_agent.adapters.persistence.memory.sessions import InMemorySessionStore
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import CO, PT, scenario_data, txn
from bank_agent_workflow_support import Backend, cases
from bank_agent_workflows import build_harness


def usd_backend() -> Backend:
    """The shared scenario data plus one USD card purchase each for the es-CO and pt personas."""
    data = scenario_data()
    usd = Currency.USD
    extra = [
        txn("TRX-FIXCO-0003", CO, "PRD-FIXCO-CRED", "261.15", usd, "2026-06-14", "EMPRESA TELEFONICA"),
        txn("TRX-FIXPT-0004", PT, "PRD-FIXPT-CRED", "600.00", usd, "2026-06-15", "POSTO EXPRESSO"),
    ]
    store = InMemoryStore()
    store.seed(
        customers=data.customers,
        products=data.products,
        transactions=[*data.transactions, *extra],
        cases=data.cases,
        credit_profiles=data.credit_profiles,
    )
    return Backend(InMemoryUnitOfWorkFactory(store), InMemorySessionStore())


async def test_es_co_usd_charge_under_the_converted_limit_reaches_the_confirmation_summary() -> None:
    backend = usd_backend()
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(CO, step_up=True)
    first = await harness.say("No reconozco un cargo de 261.15 dólares en EMPRESA TELEFONICA del 14 de junio", session)
    assert first.state == "OFFER_PROTECTIVE_BLOCK"
    summary = await harness.say("no", session, first.conversation_id)
    assert summary.state == "CONFIRM_SUMMARY"
    assert summary.response.confirmation is not None
    assert str(summary.response.confirmation.amount.amount) == "261.15"
    assert summary.response.confirmation.amount.currency.value == "USD"
    record = await harness.record(session, summary.turn_id)
    limit = [
        result
        for decision in record.decisions
        for result in decision.rule_results
        if result.rule_id == "DSP.amount_within_auto_limit"
    ]
    assert limit
    assert limit[-1].passed
    assert limit[-1].rule_version == 2
    assert limit[-1].params["compared_amount"] == Money.of("1044600.00", Currency.COP)
    assert limit[-1].params["usd_exchange_rate_as_of"] == "2026-06-11"
    assert "synthetic" in str(limit[-1].params["usd_exchange_rate_source"])
    done = await harness.say("sí", session, first.conversation_id)
    assert done.outcome is Outcome.RESOLVED
    assert "TRX-FIXCO-0003" in [case.transaction_id for case in await cases(harness, session)]


async def test_pt_usd_charge_over_the_converted_limit_escalates_with_the_rate_recorded() -> None:
    backend = usd_backend()
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT, step_up=True)
    first = await harness.say("Não reconheço uma compra de 600 dólares no POSTO EXPRESSO", session)
    assert first.state == "OFFER_PROTECTIVE_BLOCK"
    reply = await harness.say("não", session, first.conversation_id)
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert "DSP-MX-3@2" in [str(c.clause) for c in reply.response.citations]
    record = await harness.record(session, reply.turn_id)
    limit = [
        result
        for decision in record.decisions
        for result in decision.rule_results
        if result.rule_id == "DSP.amount_within_auto_limit" and not result.passed
    ]
    assert limit[-1].reason_code == "amount_above_auto_limit"
    assert limit[-1].params["compared_amount"] == Money.of("11100.00", Currency.MXN)
    assert record.handoff_ref is not None
    handoff = await harness.handoff(session, record.handoff_ref)
    assert handoff.handoff.escalation_reason.code.value == "amount_above_auto_limit"
