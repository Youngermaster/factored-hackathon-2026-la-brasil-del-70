from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from bank_agent.domain.errors import CurrencyMismatchError, ExchangeRateMismatchError, MoneyPrecisionError
from bank_agent.domain.money import Currency, ExchangeRate, Money

MXN = Currency.MXN
COP = Currency.COP

# Amounts within the dataset's DECIMAL(15,2) range.
amounts = st.decimals(min_value=Decimal("-9999999999999.99"), max_value=Decimal("9999999999999.99"), places=2)


def mxn(amount: str) -> Money:
    return Money.of(amount, MXN)


def test_adds_and_subtracts_within_one_currency() -> None:
    assert mxn("0.10") + mxn("0.20") == mxn("0.30")
    assert mxn("5.00") - mxn("7.25") == mxn("-2.25")
    assert -mxn("3.10") == mxn("-3.10")


def test_rejects_arithmetic_across_currencies() -> None:
    with pytest.raises(CurrencyMismatchError):
        _ = mxn("1") + Money.of("1", COP)
    with pytest.raises(CurrencyMismatchError):
        _ = mxn("1") - Money.of("1", COP)


@pytest.mark.parametrize("operation", ["lt", "le", "gt", "ge"])
def test_rejects_comparison_across_currencies(operation: str) -> None:
    with pytest.raises(CurrencyMismatchError):
        getattr(mxn("1"), f"__{operation}__")(Money.of("1", COP))


def test_compares_within_one_currency() -> None:
    assert mxn("1") < mxn("2")
    assert mxn("2") <= mxn("2.00")
    assert mxn("3") > mxn("2")
    assert mxn("3") >= mxn("3")


@pytest.mark.parametrize("value", [1.5, float("nan"), True])
def test_rejects_float_and_bool_amounts(value: object) -> None:
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": value, "currency": "MXN"})


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_rejects_non_finite_amounts(value: str) -> None:
    with pytest.raises(ValidationError):
        Money.of(value, MXN)


def test_multiplies_by_int_or_decimal_only() -> None:
    assert mxn("2.50") * 3 == mxn("7.50")
    assert mxn("2.50") * Decimal("0.5") == mxn("1.25")
    with pytest.raises(TypeError):
        _ = mxn("2.50") * 1.5  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = mxn("2.50") * True


def test_raises_instead_of_rounding_an_inexact_result() -> None:
    huge = Money.of(Decimal("1E+40"), MXN)
    with pytest.raises(MoneyPrecisionError):
        _ = huge + mxn("0.01")


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("0.125", "0.12"),
        ("0.135", "0.14"),
        ("-0.125", "-0.12"),
        ("2.345", "2.34"),
        ("2.355", "2.36"),
        ("10", "10.00"),
    ],
)
def test_rounds_half_to_even(amount: str, expected: str) -> None:
    rounded = mxn(amount).rounded()
    assert rounded.amount == Decimal(expected)
    assert str(rounded.amount) == expected


def test_zero_and_is_zero() -> None:
    assert Money.zero(COP).is_zero
    assert not mxn("0.01").is_zero


def test_serializes_amount_as_a_string() -> None:
    money = mxn("12.50")
    assert money.model_dump(mode="json") == {"amount": "12.50", "currency": "MXN"}
    assert Money.model_validate_json(money.model_dump_json()) == money


def test_converts_explicitly_through_an_exchange_rate() -> None:
    rate = ExchangeRate(source=Currency.USD, target=MXN, rate=Decimal("17.123456"), as_of=date(2026, 6, 1))
    converted = rate.convert(Money.of("10.00", Currency.USD))
    assert converted == Money.of("171.23456", MXN)
    assert converted.rounded() == mxn("171.23")


def test_rejects_conversion_from_the_wrong_currency() -> None:
    rate = ExchangeRate(source=Currency.USD, target=MXN, rate=Decimal(17), as_of=date(2026, 6, 1))
    with pytest.raises(ExchangeRateMismatchError):
        rate.convert(Money.of("1", COP))


@pytest.mark.parametrize(("source", "rate"), [(MXN, "17"), (Currency.USD, "0"), (Currency.USD, "-1")])
def test_rejects_invalid_exchange_rates(source: Currency, rate: str) -> None:
    with pytest.raises(ValidationError):
        ExchangeRate(source=source, target=MXN, rate=Decimal(rate), as_of=date(2026, 6, 1))


@given(amounts, amounts, amounts)
def test_addition_is_associative_within_a_currency(a: Decimal, b: Decimal, c: Decimal) -> None:
    x, y, z = Money.of(a, MXN), Money.of(b, MXN), Money.of(c, MXN)
    assert (x + y) + z == x + (y + z)


@given(amounts, amounts)
def test_addition_is_commutative_within_a_currency(a: Decimal, b: Decimal) -> None:
    assert Money.of(a, MXN) + Money.of(b, MXN) == Money.of(b, MXN) + Money.of(a, MXN)


@given(st.decimals(min_value=Decimal(-(10**12)), max_value=Decimal(10**12), places=6))
def test_rounding_is_idempotent(amount: Decimal) -> None:
    once = Money.of(amount, MXN).rounded()
    assert once.rounded() == once
