"""Read-only views for account and payment inquiries: balances, payment status, and statement summaries.

Every view is built from records the customer owns and carries source references, so the grounding verifier
can check each number against a record. The dataset is a monthly snapshot: every balance states its as-of
instant. There are no statement balances in the data, so a statement summary never shows an opening or a
closing balance, and there is no document generation or delivery.

Two conventions depend on how the data encodes signs, which phase 03 profiles:

- whether a credit product's ``current_balance`` is the amount owed or is negative when owed
  (``CreditBalanceConvention``; there is deliberately no default), and
- the direction of transfers and adjustments, which stay ``unclassified`` in statement totals.
"""

import re
from collections.abc import Callable, Iterable
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, NonNegativeInt, model_validator

from bank_agent.domain.base import DisplayText, DomainModel, UtcDatetime
from bank_agent.domain.identifiers import SourceRef, SourceTable
from bank_agent.domain.intelligence import DateRange
from bank_agent.domain.masking import MaskedNumber
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.product import CREDIT_PRODUCT_TYPES, Product, ProductType
from bank_agent.domain.transaction import Transaction, TransactionStatus, TransactionType

MAX_STATEMENT_LINES = 20
MAX_STATEMENT_DAYS = 366
_CONTROL_OR_SPACE = re.compile(r"[\x00-\x1F\x7F\s]+")


def display_text(value: str | None) -> str | None:
    """Sanitize record text for display: control characters and runs of whitespace become one space, and the
    result is trimmed to 150 characters. The text stays untrusted and is rendered as plain text only."""
    if value is None:
        return None
    cleaned = _CONTROL_OR_SPACE.sub(" ", value).strip()[:150].strip()
    return cleaned or None


def _require_table(ref: SourceRef, table: SourceTable, name: str) -> None:
    if ref.table is not table:
        raise ValueError(f"{name} must reference the {table.value} table")


# --- Balances ------------------------------------------------------------------------------------------------


class CreditBalanceConvention(StrEnum):
    """How a credit product's ``current_balance`` encodes debt. Phase 03 records which one the data uses."""

    BALANCE_IS_AMOUNT_OWED = "balance_is_amount_owed"
    BALANCE_IS_NEGATIVE_WHEN_OWED = "balance_is_negative_when_owed"


class AvailableCredit(DomainModel):
    amount: Money
    over_limit: bool


def available_credit(limit: Money, balance: Money, convention: CreditBalanceConvention) -> AvailableCredit:
    """The credit still available under ``limit``, floored at zero; ``over_limit`` is true when the debt exceeds it.

    Raises ``CurrencyMismatchError`` when the limit and the balance use different currencies.
    """
    owed = balance if convention is CreditBalanceConvention.BALANCE_IS_AMOUNT_OWED else -balance
    remaining = limit - owed
    if remaining.amount < 0:
        return AvailableCredit(amount=Money.zero(limit.currency), over_limit=True)
    return AvailableCredit(amount=remaining, over_limit=False)


class BalanceView(DomainModel):
    """One product's balance. ``product_ref`` is grounding evidence; the chat shows only the masked number."""

    product_ref: SourceRef
    product_type: ProductType
    masked_number: MaskedNumber
    current_balance: Money
    credit_limit: Money | None = None
    available_credit: Money | None = None
    over_limit: bool = False
    as_of: UtcDatetime

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _require_table(self.product_ref, SourceTable.PRODUCTS, "product_ref")
        currency = self.current_balance.currency
        for amount in (self.credit_limit, self.available_credit):
            if amount is not None and amount.currency is not currency:
                raise ValueError("every amount in a balance view uses one currency")
        if self.available_credit is not None and self.credit_limit is None:
            raise ValueError("available credit needs a known credit limit")
        if self.over_limit and self.available_credit is None:
            raise ValueError("over_limit is only known together with the available credit")
        return self

    @classmethod
    def from_product(cls, product: Product, convention: CreditBalanceConvention | None = None) -> Self:
        """Build the view from a product that has a balance.

        ``available_credit`` is computed only for a credit product with a limit and only when a convention is
        given. Raises ``ValueError`` when the product has no balance.
        """
        if product.current_balance is None or product.balance_as_of is None:
            raise ValueError("the product has no balance")
        available: AvailableCredit | None = None
        if convention is not None and product.credit_limit is not None and product.is_credit_product:
            available = available_credit(product.credit_limit, product.current_balance, convention)
        return cls(
            product_ref=SourceRef.of(SourceTable.PRODUCTS, product.product_id),
            product_type=product.product_type,
            masked_number=product.masked_number,
            current_balance=product.current_balance,
            credit_limit=product.credit_limit,
            available_credit=available.amount if available is not None else None,
            over_limit=available.over_limit if available is not None else False,
            as_of=product.balance_as_of,
        )


# --- Payment status ------------------------------------------------------------------------------------------

PAYMENT_TYPES = frozenset({TransactionType.PAYMENT, TransactionType.TRANSFER})


class PaymentStatusView(DomainModel):
    """The status of one payment or transfer. ``payee_display`` is sanitized record text, never an instruction."""

    transaction_ref: SourceRef
    transaction_type: TransactionType
    status: TransactionStatus
    amount: Money
    occurred_on: date
    payee_display: DisplayText | None = None
    masked_number: MaskedNumber

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _require_table(self.transaction_ref, SourceTable.TRANSACTIONS, "transaction_ref")
        if self.transaction_type not in PAYMENT_TYPES:
            raise ValueError("a payment status covers payments and transfers only")
        return self

    @classmethod
    def from_transaction(cls, transaction: Transaction, product: Product, *, occurred_on: date) -> Self:
        """Build the view. ``occurred_on`` is the local date in the customer's time zone (the application
        converts it, because the domain never touches the time zone database)."""
        if transaction.product_id != product.product_id:
            raise ValueError("the transaction must belong to the product")
        return cls(
            transaction_ref=SourceRef.of(SourceTable.TRANSACTIONS, transaction.transaction_id),
            transaction_type=transaction.transaction_type,
            status=transaction.status,
            amount=transaction.amount,
            occurred_on=occurred_on,
            payee_display=display_text(transaction.merchant_name),
            masked_number=product.masked_number,
        )


# --- Statement summaries -------------------------------------------------------------------------------------


class EntryDirection(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"
    UNCLASSIFIED = "unclassified"
    """The data does not say which way the money moved (transfers and adjustments)."""


def direction_of(product_type: ProductType, transaction_type: TransactionType) -> EntryDirection:
    """Which way a transaction moves the product's balance.

    A deposit is a credit; a purchase or a withdrawal is a debit; a payment is a credit on a credit product
    (it reduces the debt) and a debit on any other product. Transfers and adjustments are unclassified until
    phase 03 profiles the amount signs.
    """
    if transaction_type is TransactionType.DEPOSIT:
        return EntryDirection.CREDIT
    if transaction_type in (TransactionType.PURCHASE, TransactionType.WITHDRAWAL):
        return EntryDirection.DEBIT
    if transaction_type is TransactionType.PAYMENT:
        return EntryDirection.CREDIT if product_type in CREDIT_PRODUCT_TYPES else EntryDirection.DEBIT
    return EntryDirection.UNCLASSIFIED


class StatementPeriod(DomainModel):
    product_ref: SourceRef
    dates: DateRange

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _require_table(self.product_ref, SourceTable.PRODUCTS, "product_ref")
        if (self.dates.end - self.dates.start).days + 1 > MAX_STATEMENT_DAYS:
            raise ValueError(f"a statement period covers at most {MAX_STATEMENT_DAYS} days")
        return self

    def contains(self, day: date) -> bool:
        return self.dates.start <= day <= self.dates.end


class CurrencyTotals(DomainModel):
    """Settled debits and credits in one currency. Amounts in different currencies are never added together."""

    currency: Currency
    debits: Money
    credits: Money
    debit_count: NonNegativeInt = 0
    credit_count: NonNegativeInt = 0

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.debits.currency is not self.currency or self.credits.currency is not self.currency:
            raise ValueError("totals must be in their own currency")
        return self

    @classmethod
    def zero(cls, currency: Currency) -> Self:
        return cls(currency=currency, debits=Money.zero(currency), credits=Money.zero(currency))

    def plus(self, other: "CurrencyTotals") -> "CurrencyTotals":
        """Add totals in the same currency; different currencies raise ``CurrencyMismatchError``."""
        return CurrencyTotals(
            currency=self.currency,
            debits=self.debits + other.debits,
            credits=self.credits + other.credits,
            debit_count=self.debit_count + other.debit_count,
            credit_count=self.credit_count + other.credit_count,
        )

    def with_entry(self, direction: EntryDirection, amount: Money) -> "CurrencyTotals":
        if direction is EntryDirection.DEBIT:
            return self.evolve(debits=self.debits + amount, debit_count=self.debit_count + 1)
        if direction is EntryDirection.CREDIT:
            return self.evolve(credits=self.credits + amount, credit_count=self.credit_count + 1)
        raise ValueError("unclassified entries have no total")


def settled_totals(product_type: ProductType, transactions: Iterable[Transaction]) -> tuple[CurrencyTotals, ...]:
    """Totals per currency, ordered by currency code, over the approved and classified transactions."""
    totals: dict[Currency, CurrencyTotals] = {}
    for transaction in transactions:
        direction = direction_of(product_type, transaction.transaction_type)
        if transaction.status is not TransactionStatus.APPROVED or direction is EntryDirection.UNCLASSIFIED:
            continue
        currency = transaction.amount.currency
        current = totals.get(currency, CurrencyTotals.zero(currency))
        totals[currency] = current.with_entry(direction, transaction.amount)
    return tuple(totals[currency] for currency in sorted(totals))


class StatementLine(DomainModel):
    occurred_on: date
    transaction_type: TransactionType
    direction: EntryDirection
    amount: Money
    status: TransactionStatus
    display_text: DisplayText | None = None
    source: SourceRef

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _require_table(self.source, SourceTable.TRANSACTIONS, "source")
        return self


class StatementSummary(DomainModel):
    """A summary of one product's transactions in a period.

    ``totals`` cover approved transactions whose direction is known, one entry per currency.
    ``unclassified_count`` counts approved transfers and adjustments; ``not_settled_count`` counts pending,
    declined, and reversed transactions. At most ``MAX_STATEMENT_LINES`` lines are listed, newest first.
    """

    period: StatementPeriod
    transaction_count: NonNegativeInt
    totals: tuple[CurrencyTotals, ...] = ()
    unclassified_count: NonNegativeInt = 0
    not_settled_count: NonNegativeInt = 0
    lines: Annotated[tuple[StatementLine, ...], Field(max_length=MAX_STATEMENT_LINES)] = ()
    truncated: bool = False
    as_of: UtcDatetime
    sources: tuple[SourceRef, ...]

    @model_validator(mode="after")
    def _validate(self) -> Self:
        currencies = [totals.currency for totals in self.totals]
        if len(currencies) != len(set(currencies)):
            raise ValueError("a statement has one totals entry per currency")
        classified = sum(totals.debit_count + totals.credit_count for totals in self.totals)
        if self.transaction_count != classified + self.unclassified_count + self.not_settled_count:
            raise ValueError("transaction_count must equal the classified, unclassified, and unsettled counts")
        if self.truncated != (self.transaction_count > len(self.lines)):
            raise ValueError("truncated is true exactly when some transactions are not listed")
        if len(self.lines) > self.transaction_count:
            raise ValueError("a statement cannot list more lines than it has transactions")
        if self.period.product_ref not in self.sources:
            raise ValueError("the statement's sources include its product")
        return self

    @classmethod
    def from_transactions(
        cls,
        period: StatementPeriod,
        product: Product,
        transactions: Iterable[Transaction],
        *,
        as_of: datetime,
        local_date: Callable[[datetime], date],
    ) -> Self:
        """Summarize the product's transactions whose local date falls in the period.

        ``local_date`` converts an instant to the customer's calendar date (supplied by the application).
        Transactions of other products or outside the period are ignored.
        """
        if period.product_ref != SourceRef.of(SourceTable.PRODUCTS, product.product_id):
            raise ValueError("the period must be for the product")
        included = sorted(
            (
                txn
                for txn in transactions
                if txn.product_id == product.product_id and period.contains(local_date(txn.occurred_at))
            ),
            key=lambda txn: (txn.occurred_at, txn.transaction_id),
            reverse=True,
        )
        settled = [txn for txn in included if txn.status is TransactionStatus.APPROVED]
        unclassified = [
            txn
            for txn in settled
            if direction_of(product.product_type, txn.transaction_type) is EntryDirection.UNCLASSIFIED
        ]
        lines = tuple(
            StatementLine(
                occurred_on=local_date(txn.occurred_at),
                transaction_type=txn.transaction_type,
                direction=direction_of(product.product_type, txn.transaction_type),
                amount=txn.amount,
                status=txn.status,
                display_text=display_text(txn.merchant_name),
                source=SourceRef.of(SourceTable.TRANSACTIONS, txn.transaction_id),
            )
            for txn in included[:MAX_STATEMENT_LINES]
        )
        return cls(
            period=period,
            transaction_count=len(included),
            totals=settled_totals(product.product_type, settled),
            unclassified_count=len(unclassified),
            not_settled_count=len(included) - len(settled),
            lines=lines,
            truncated=len(included) > len(lines),
            as_of=as_of,
            sources=(period.product_ref, *(line.source for line in lines)),
        )
