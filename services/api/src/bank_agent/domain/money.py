"""Money and currency.

Amounts are ``Decimal``, never ``float``. Arithmetic is allowed only between amounts in the same currency, and
conversion between currencies happens only through an explicit ``ExchangeRate``. Addition, subtraction, and
multiplication run in an exact decimal context: a result that cannot be represented exactly raises
``MoneyPrecisionError`` instead of being rounded silently. Rounding happens only when ``rounded()`` is called,
with banker's rounding (round half to even) to the currency's minor units. See ADR 0004.
"""

from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal, DivisionByZero, Inexact, InvalidOperation, Overflow
from enum import StrEnum
from typing import Annotated, Self

from pydantic import AfterValidator, BeforeValidator, model_validator

from bank_agent.domain.base import DomainModel
from bank_agent.domain.errors import CurrencyMismatchError, ExchangeRateMismatchError, MoneyPrecisionError


class Currency(StrEnum):
    MXN = "MXN"
    COP = "COP"
    ARS = "ARS"
    USD = "USD"

    @property
    def minor_units(self) -> int:
        """Digits after the decimal point in ISO 4217. All four currencies use 2."""
        return 2


MONEY_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN, traps=[InvalidOperation, DivisionByZero, Overflow])
"""Context for explicit rounding."""

EXACT_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN, traps=[InvalidOperation, DivisionByZero, Overflow, Inexact])
"""Context for arithmetic: any inexact result raises instead of rounding."""


def _reject_inexact_types(value: object) -> object:
    if isinstance(value, bool | float):
        raise ValueError("amounts must be Decimal, int, or a decimal string, never float or bool")
    return value


def _require_finite(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("amounts must be finite")
    return value


Amount = Annotated[Decimal, BeforeValidator(_reject_inexact_types), AfterValidator(_require_finite)]
"""A finite ``Decimal``. Floats and booleans are rejected; JSON carries amounts as strings."""


def _exact(operation: Callable[[Decimal, Decimal], Decimal], left: Decimal, right: Decimal) -> Decimal:
    try:
        return operation(left, right)
    except Inexact as error:
        raise MoneyPrecisionError() from error


class Money(DomainModel):
    """An amount in one currency. JSON form: ``{"amount": "12.50", "currency": "MXN"}``."""

    amount: Amount
    currency: Currency

    @classmethod
    def of(cls, amount: Decimal | int | str, currency: Currency) -> Self:
        return cls.model_validate({"amount": amount, "currency": currency})

    @classmethod
    def zero(cls, currency: Currency) -> Self:
        return cls(amount=Decimal(0), currency=currency)

    def _require_same_currency(self, other: "Money") -> None:
        if other.currency is not self.currency:
            raise CurrencyMismatchError(f"cannot combine {self.currency} with {other.currency}")

    def __add__(self, other: "Money") -> "Money":
        self._require_same_currency(other)
        return Money(amount=_exact(EXACT_CONTEXT.add, self.amount, other.amount), currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._require_same_currency(other)
        return Money(amount=_exact(EXACT_CONTEXT.subtract, self.amount, other.amount), currency=self.currency)

    def __neg__(self) -> "Money":
        return Money(amount=EXACT_CONTEXT.minus(self.amount), currency=self.currency)

    def __mul__(self, factor: int | Decimal) -> "Money":
        if isinstance(factor, bool) or not isinstance(factor, int | Decimal):
            raise TypeError("money can only be multiplied by an int or a Decimal")
        return Money(amount=_exact(EXACT_CONTEXT.multiply, self.amount, Decimal(factor)), currency=self.currency)

    def __lt__(self, other: "Money") -> bool:
        self._require_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        self._require_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: "Money") -> bool:
        self._require_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: "Money") -> bool:
        self._require_same_currency(other)
        return self.amount >= other.amount

    @property
    def is_zero(self) -> bool:
        return self.amount.is_zero()

    def rounded(self) -> "Money":
        """Quantize to the currency's minor units with banker's rounding (0.125 becomes 0.12, 0.135 becomes 0.14)."""
        exponent = Decimal(1).scaleb(-self.currency.minor_units)
        return Money(
            amount=self.amount.quantize(exponent, rounding=ROUND_HALF_EVEN, context=MONEY_CONTEXT),
            currency=self.currency,
        )


class ExchangeRate(DomainModel):
    """One unit of ``source`` is worth ``rate`` units of ``target`` on ``as_of``."""

    source: Currency
    target: Currency
    rate: Amount
    as_of: date

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.source is self.target:
            raise ValueError("an exchange rate needs two different currencies")
        if self.rate <= 0:
            raise ValueError("an exchange rate must be positive")
        return self

    def convert(self, money: Money) -> Money:
        """Convert ``money`` to the target currency, unrounded. The caller rounds explicitly."""
        if money.currency is not self.source:
            raise ExchangeRateMismatchError(f"rate converts {self.source}, not {money.currency}")
        return Money(amount=_exact(EXACT_CONTEXT.multiply, money.amount, self.rate), currency=self.target)
