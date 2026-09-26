from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from bank_agent.domain.accounts import (
    MAX_STATEMENT_LINES,
    BalanceView,
    CreditBalanceConvention,
    CurrencyTotals,
    EntryDirection,
    PaymentStatusView,
    StatementPeriod,
    StatementSummary,
    available_credit,
    direction_of,
    display_text,
    settled_totals,
)
from bank_agent.domain.base import internal_fields
from bank_agent.domain.errors import CurrencyMismatchError
from bank_agent.domain.identifiers import SourceRef
from bank_agent.domain.intelligence import DateRange
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.product import Product, ProductStatus, ProductType
from bank_agent.domain.transaction import Transaction, TransactionStatus, TransactionType
from bank_agent_builders import T0, product, transaction

MXN = Currency.MXN


def mxn(amount: str) -> Money:
    return Money.of(amount, MXN)


def card(**extra: Any) -> Product:
    fields: dict[str, Any] = {
        "current_balance": mxn("8450.00"),
        "credit_limit": mxn("20000.00"),
        "balance_as_of": T0,
    }
    return product(**{**fields, **extra})


def utc_date(instant: datetime) -> date:
    return instant.astimezone(UTC).date()


# --- Product -------------------------------------------------------------------------------------------------


def test_product_balance_fields_are_optional() -> None:
    plain = product()
    assert plain.current_balance is None
    assert plain.credit_limit is None
    assert plain.days_past_due is None


def test_product_amounts_use_the_product_currency() -> None:
    with pytest.raises(ValidationError, match="product currency"):
        card(credit_limit=Money.of("100", Currency.USD))
    with pytest.raises(ValidationError, match="product currency"):
        card(current_balance=Money.of("100", Currency.COP))


def test_a_balance_needs_its_as_of_instant() -> None:
    with pytest.raises(ValidationError, match="balance_as_of"):
        product(current_balance=mxn("1"))
    assert product(credit_limit=mxn("100")).balance_as_of is None


def test_rate_bounds_allow_rates_above_one_hundred_percent() -> None:
    assert product(annual_interest_rate=Decimal("120.50")).annual_interest_rate == Decimal("120.50")
    with pytest.raises(ValidationError):
        product(annual_interest_rate=Decimal("1000.00"))
    with pytest.raises(ValidationError):
        product(annual_interest_rate=Decimal(-1))
    with pytest.raises(ValidationError):
        product(annual_interest_rate=45.0)


def test_rejects_a_negative_credit_limit() -> None:
    with pytest.raises(ValidationError, match="negative"):
        product(credit_limit=mxn("-1"))


def test_days_past_due_is_internal() -> None:
    assert "days_past_due" in internal_fields(Product)
    with pytest.raises(ValidationError):
        product(days_past_due=-1)


def test_blocking_keeps_the_balance_fields() -> None:
    blocked = card(days_past_due=3).blocked()
    assert blocked.status is ProductStatus.BLOCKED
    assert blocked.current_balance == mxn("8450.00")
    assert blocked.days_past_due == 3


# --- Balances ------------------------------------------------------------------------------------------------


def test_available_credit_under_both_conventions() -> None:
    owed = available_credit(mxn("20000"), mxn("8450"), CreditBalanceConvention.BALANCE_IS_AMOUNT_OWED)
    assert owed.amount == mxn("11550")
    assert not owed.over_limit
    negative = available_credit(mxn("20000"), mxn("-8450"), CreditBalanceConvention.BALANCE_IS_NEGATIVE_WHEN_OWED)
    assert negative.amount == mxn("11550")


def test_available_credit_is_floored_at_zero_over_the_limit() -> None:
    result = available_credit(mxn("1000"), mxn("1200"), CreditBalanceConvention.BALANCE_IS_AMOUNT_OWED)
    assert result.amount == mxn("0")
    assert result.over_limit


def test_available_credit_never_mixes_currencies() -> None:
    with pytest.raises(CurrencyMismatchError):
        available_credit(mxn("1000"), Money.of("1", Currency.USD), CreditBalanceConvention.BALANCE_IS_AMOUNT_OWED)


def test_balance_view_without_a_convention_leaves_available_credit_unknown() -> None:
    view = BalanceView.from_product(card())
    assert view.available_credit is None
    assert view.credit_limit == mxn("20000.00")
    assert view.as_of == T0
    assert str(view.product_ref) == "products:PRD-A-CARD"


def test_balance_view_with_a_convention_computes_available_credit() -> None:
    view = BalanceView.from_product(card(), CreditBalanceConvention.BALANCE_IS_AMOUNT_OWED)
    assert view.available_credit == mxn("11550.00")


def test_balance_view_of_a_deposit_account_has_no_available_credit() -> None:
    savings = product(
        "PRD-A-SAVE", product_type=ProductType.SAVINGS_ACCOUNT, current_balance=mxn("15200"), balance_as_of=T0
    )
    view = BalanceView.from_product(savings, CreditBalanceConvention.BALANCE_IS_AMOUNT_OWED)
    assert view.available_credit is None
    assert view.credit_limit is None


def test_balance_view_needs_a_balance() -> None:
    with pytest.raises(ValueError, match="no balance"):
        BalanceView.from_product(product())


def test_balance_view_rejects_inconsistent_parts() -> None:
    view = BalanceView.from_product(card(), CreditBalanceConvention.BALANCE_IS_AMOUNT_OWED)
    with pytest.raises(ValidationError, match="known credit limit"):
        view.evolve(credit_limit=None)
    with pytest.raises(ValidationError, match="one currency"):
        view.evolve(available_credit=Money.of("1", Currency.USD))
    with pytest.raises(ValidationError, match="products table"):
        view.evolve(product_ref=SourceRef.model_validate("transactions:TXN-1"))
    with pytest.raises(ValidationError, match="over_limit"):
        view.evolve(available_credit=None, over_limit=True)


# --- Payment status ------------------------------------------------------------------------------------------


def test_payment_status_view_from_a_payment() -> None:
    payment = transaction(
        "TXN-A-0004",
        transaction_type=TransactionType.PAYMENT,
        status=TransactionStatus.PENDING,
        merchant_name="  PAGO\nSERVICIOS\t LUZ ",
    )
    view = PaymentStatusView.from_transaction(payment, card(), occurred_on=date(2026, 5, 31))
    assert view.status is TransactionStatus.PENDING
    assert view.payee_display == "PAGO SERVICIOS LUZ"
    assert view.masked_number.last4 == "1234"


def test_payment_status_covers_only_payments_and_transfers() -> None:
    with pytest.raises(ValidationError, match="payments and transfers"):
        PaymentStatusView.from_transaction(transaction(), card(), occurred_on=date(2026, 6, 7))


def test_payment_status_needs_the_transactions_product() -> None:
    other = transaction(product_id="PRD-A-SAVE", transaction_type=TransactionType.TRANSFER)
    with pytest.raises(ValueError, match="belong to the product"):
        PaymentStatusView.from_transaction(other, card(), occurred_on=date(2026, 6, 7))


def test_display_text_is_sanitized() -> None:
    assert display_text(None) is None
    assert display_text(" \n\t ") is None
    assert display_text("A\x00B\r\nC") == "A B C"
    assert display_text("x" * 200) == "x" * 150


# --- Statements ----------------------------------------------------------------------------------------------


def period(start: int = 1, end: int = 30) -> StatementPeriod:
    return StatementPeriod(
        product_ref=SourceRef.model_validate("products:PRD-A-CARD"),
        dates=DateRange(start=date(2026, 6, start), end=date(2026, 6, end)),
    )


def at(day: int) -> datetime:
    return datetime(2026, 6, day, 12, tzinfo=UTC)


def test_direction_table() -> None:
    card_type = ProductType.CREDIT_CARD
    checking = ProductType.CHECKING_ACCOUNT
    assert direction_of(card_type, TransactionType.PURCHASE) is EntryDirection.DEBIT
    assert direction_of(checking, TransactionType.WITHDRAWAL) is EntryDirection.DEBIT
    assert direction_of(checking, TransactionType.DEPOSIT) is EntryDirection.CREDIT
    assert direction_of(card_type, TransactionType.PAYMENT) is EntryDirection.CREDIT
    assert direction_of(checking, TransactionType.PAYMENT) is EntryDirection.DEBIT
    assert direction_of(checking, TransactionType.TRANSFER) is EntryDirection.UNCLASSIFIED
    assert direction_of(card_type, TransactionType.ADJUSTMENT) is EntryDirection.UNCLASSIFIED


def test_statement_totals_per_currency_never_mixed() -> None:
    transactions = [
        transaction("T1", occurred_at=at(3), amount="100.00"),
        transaction("T2", occurred_at=at(4), amount="50.00", currency=Currency.USD),
        transaction("T3", occurred_at=at(5), amount="30.00", transaction_type=TransactionType.PAYMENT),
        transaction("T4", occurred_at=at(6), amount="20.00", transaction_type=TransactionType.TRANSFER),
        transaction("T5", occurred_at=at(7), amount="10.00", status=TransactionStatus.DECLINED),
        transaction("T6", occurred_at=datetime(2026, 7, 2, tzinfo=UTC), amount="999.00"),
        transaction("T7", product_id="PRD-A-SAVE", occurred_at=at(8)),
    ]
    summary = StatementSummary.from_transactions(period(), card(), transactions, as_of=T0, local_date=utc_date)
    assert summary.transaction_count == 5
    assert [t.currency for t in summary.totals] == [Currency.MXN, Currency.USD]
    mxn_totals, usd_totals = summary.totals
    assert (mxn_totals.debits, mxn_totals.credits) == (mxn("100.00"), mxn("30.00"))
    assert usd_totals.debits == Money.of("50.00", Currency.USD)
    assert (summary.unclassified_count, summary.not_settled_count) == (1, 1)
    assert [line.source.key for line in summary.lines] == ["T5", "T4", "T3", "T2", "T1"]
    assert not summary.truncated
    assert summary.sources[0] == period().product_ref


def test_statement_lists_at_most_twenty_lines() -> None:
    transactions = [transaction(f"T{i:02d}", occurred_at=at(1) + timedelta(hours=i), amount="1.00") for i in range(25)]
    summary = StatementSummary.from_transactions(period(), card(), transactions, as_of=T0, local_date=utc_date)
    assert len(summary.lines) == MAX_STATEMENT_LINES
    assert summary.truncated
    assert summary.lines[0].source.key == "T24"
    assert summary.totals[0].debits == mxn("25.00")


def test_statement_has_no_balance_field() -> None:
    assert not {"opening_balance", "closing_balance", "balance"} & set(StatementSummary.model_fields)


def test_statement_invariants() -> None:
    summary = StatementSummary.from_transactions(
        period(), card(), [transaction("T1", occurred_at=at(3))], as_of=T0, local_date=utc_date
    )
    with pytest.raises(ValidationError, match="transaction_count"):
        summary.evolve(transaction_count=2, truncated=True)
    with pytest.raises(ValidationError, match="truncated"):
        summary.evolve(truncated=True)
    with pytest.raises(ValidationError, match="one totals entry"):
        summary.evolve(totals=summary.totals * 2)
    with pytest.raises(ValidationError, match="include its product"):
        summary.evolve(sources=summary.sources[1:])
    with pytest.raises(ValueError, match="for the product"):
        StatementSummary.from_transactions(period(), product("PRD-A-SAVE"), [], as_of=T0, local_date=utc_date)


def test_statement_period_is_bounded() -> None:
    with pytest.raises(ValidationError, match="366 days"):
        StatementPeriod(
            product_ref=SourceRef.model_validate("products:P1"),
            dates=DateRange(start=date(2025, 1, 1), end=date(2026, 1, 2)),
        )


def test_currency_totals_stay_in_their_currency() -> None:
    with pytest.raises(ValidationError, match="own currency"):
        CurrencyTotals(currency=MXN, debits=Money.zero(Currency.USD), credits=Money.zero(MXN))
    with pytest.raises(CurrencyMismatchError):
        CurrencyTotals.zero(MXN).plus(CurrencyTotals.zero(Currency.USD))
    with pytest.raises(ValueError, match="unclassified"):
        CurrencyTotals.zero(MXN).with_entry(EntryDirection.UNCLASSIFIED, mxn("1"))


_amounts = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("99999.99"), places=2)
_entries = st.lists(
    st.tuples(
        _amounts,
        st.sampled_from([Currency.MXN, Currency.USD]),
        st.sampled_from([TransactionType.PURCHASE, TransactionType.PAYMENT, TransactionType.TRANSFER]),
    ),
    max_size=12,
)


def _transactions(prefix: str, entries: list[tuple[Decimal, Currency, TransactionType]]) -> list[Transaction]:
    return [
        transaction(f"{prefix}{index}", amount=str(amount), currency=currency, transaction_type=kind)
        for index, (amount, currency, kind) in enumerate(entries)
    ]


@given(_entries, _entries)
def test_statement_totals_are_additive_within_a_currency(
    left: list[tuple[Decimal, Currency, TransactionType]], right: list[tuple[Decimal, Currency, TransactionType]]
) -> None:
    a, b = _transactions("A", left), _transactions("B", right)
    combined = {t.currency: t for t in settled_totals(ProductType.CREDIT_CARD, a + b)}
    expected: dict[Currency, CurrencyTotals] = {}
    for totals in (*settled_totals(ProductType.CREDIT_CARD, a), *settled_totals(ProductType.CREDIT_CARD, b)):
        expected[totals.currency] = expected[totals.currency].plus(totals) if totals.currency in expected else totals
    assert combined == expected
