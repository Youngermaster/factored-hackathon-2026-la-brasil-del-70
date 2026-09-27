from datetime import date, timedelta
from decimal import Decimal

import pytest

from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory
from bank_agent.application.tools.auditing import REDACTED, redact_arguments
from bank_agent.application.tools.banking import BankingTools
from bank_agent.application.tools.context import SessionContext, ToolSettings
from bank_agent.domain.access import Role
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.errors import AccessContextError, SessionExpiredError, SessionRevokedError
from bank_agent.domain.identifiers import ProductId
from bank_agent.domain.intelligence import DateRange
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.transaction import Transaction, TransactionStatus
from bank_agent.testing.clock import FixedClock
from bank_agent_builders import CUSTOMER_A, T0, session, transaction
from bank_agent_contracts import contract_dataset
from bank_agent_tools import NOW, session_context, tool_dependencies


def _factory(extra_transactions: tuple[Transaction, ...] = ()) -> InMemoryUnitOfWorkFactory:
    data, store = contract_dataset(), InMemoryStore()
    store.seed(
        customers=data.customers,
        products=data.products,
        transactions=(*data.transactions, *extra_transactions),
        cases=data.cases,
        credit_profiles=data.credit_profiles,
        credit_applications=data.credit_applications,
    )
    return InMemoryUnitOfWorkFactory(store)


def test_a_context_is_refused_for_an_expired_or_revoked_session() -> None:
    with pytest.raises(SessionExpiredError, match="idle"):
        SessionContext.of(session(), FixedClock(T0 + timedelta(minutes=15)))
    with pytest.raises(SessionExpiredError, match="absolute"):
        SessionContext.of(session().evolve(idle_timeout=timedelta(hours=2)), FixedClock(T0 + timedelta(hours=1)))
    with pytest.raises(SessionRevokedError):
        SessionContext.of(session().revoked(T0), FixedClock(NOW))
    assert session_context().access.customer_id == CUSTOMER_A


def test_arguments_are_redacted_unless_allowlisted() -> None:
    redacted = redact_arguments(
        {
            "transaction_id": "TXN-A-0001",
            "reason": DisputeReason.UNRECOGNIZED,
            "declared_monthly_income": Money.of("1000", Currency.MXN),
            "statuses": (TransactionStatus.PENDING, TransactionStatus.APPROVED),
            "limit": 5,
            "period_days": 31,
        }
    )
    assert redacted == {
        "transaction_id": REDACTED,
        "reason": "unrecognized",
        "declared_monthly_income": REDACTED,
        "statuses": ["approved", "pending"],
        "limit": 5,
        "period_days": 31,
    }


async def test_statements_never_mix_currencies() -> None:
    usd = transaction("TXN-A-0100", occurred_at=T0 - timedelta(days=1), amount="10.00").evolve(
        amount=Money.of("10.00", Currency.USD)
    )
    tools = BankingTools(tool_dependencies(_factory((usd,)))).for_session(session_context())
    summary = await tools.get_statement_summary(
        ProductId("PRD-A-CARD"), DateRange(start=date(2026, 6, 1), end=date(2026, 6, 10))
    )
    assert summary is not None
    by_currency = {total.currency: total for total in summary.totals}
    assert set(by_currency) == {Currency.MXN, Currency.USD}
    assert by_currency[Currency.USD].debits == Money.of(Decimal("10.00"), Currency.USD)
    assert all(total.credits.currency is total.currency for total in summary.totals)


async def test_the_credit_profile_is_reachable_only_through_engine_only_tools() -> None:
    banking = BankingTools(tool_dependencies(_factory()))
    assert not hasattr(banking.for_session(session_context()), "get_my_credit_profile")
    profile = await banking.engine_only(session_context()).get_my_credit_profile()
    assert profile is not None
    assert profile.customer_id == CUSTOMER_A


async def test_staff_sessions_cannot_use_customer_tools() -> None:
    staff = session(customer_id=None, role=Role.AGENT, staff_id="agent-0001")
    tools = BankingTools(tool_dependencies(_factory())).for_session(SessionContext.of(staff, FixedClock(NOW)))
    with pytest.raises(AccessContextError):
        await tools.list_my_balances()


def test_local_dates_use_the_customer_time_zone() -> None:
    settings = ToolSettings()
    late_evening_utc = T0.replace(hour=3)
    assert settings.local_date(Country.MX, late_evening_utc) == date(2026, 6, 9)
    assert settings.local_date(Country.AR, late_evening_utc) == date(2026, 6, 10)
