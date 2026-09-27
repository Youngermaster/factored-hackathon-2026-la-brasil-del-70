"""Deterministic account and credit slots: product types, terms, a declared income, and purposes, in es and pt."""

from decimal import Decimal

import pytest

from bank_agent.application.understanding import slots
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.product import ProductType


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("el saldo de mi cuenta de ahorro", ProductType.SAVINGS_ACCOUNT),
        ("saldo da minha conta poupança", ProductType.SAVINGS_ACCOUNT),
        ("mi cuenta corriente", ProductType.CHECKING_ACCOUNT),
        ("estado de cuenta de mi tarjeta de crédito", ProductType.CREDIT_CARD),
        ("meu cartão de débito", ProductType.DEBIT_CARD),
        ("cuánto tengo", None),
    ],
)
def test_account_product_types(text: str, expected: ProductType | None) -> None:
    assert slots.account_product_type(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("¿califico para una hipoteca?", CreditProductType.MORTGAGE),
        ("financiamento imobiliário", CreditProductType.MORTGAGE),
        ("un cartão de crédito com limite de 30 mil", CreditProductType.CREDIT_CARD),
        ("un préstamo personal", CreditProductType.PERSONAL_LOAN),
        ("um empréstimo pessoal", CreditProductType.PERSONAL_LOAN),
    ],
)
def test_credit_product_types(text: str, expected: CreditProductType) -> None:
    assert slots.credit_product_type(text) is expected


@pytest.mark.parametrize(
    ("text", "months"),
    [("a 24 meses", 24), ("em 36 meses", 36), ("a dos años", 24), ("em 2 anos", 24), ("sin plazo", None)],
)
def test_terms_in_months(text: str, months: int | None) -> None:
    assert slots.term_months(text) == months


def test_requested_amount_and_declared_income_are_told_apart() -> None:
    found = slots.credit_amounts("Quiero 50 mil a 24 meses, gano 30 mil al mes")
    assert found.requested is not None
    assert found.requested.amount == Decimal("50000")
    assert found.income is not None
    assert found.income.amount == Decimal("30000")
    only_income = slots.credit_amounts("Minha renda é de 5 mil reais")
    assert only_income.requested is None
    assert only_income.income is not None
    assert only_income.income.amount == Decimal("5000")
    assert slots.credit_amounts("Un préstamo de 1.5 millones").income is None


@pytest.mark.parametrize(
    ("text", "purpose"),
    [
        ("para consolidar mis deudas", "debt_consolidation"),
        ("para quitar minhas dívidas", "debt_consolidation"),
        ("para remodelar la cocina", "home_improvement"),
        ("para pagar la universidad", "education"),
        ("para viajar", None),
    ],
)
def test_purposes_map_to_catalog_codes(text: str, purpose: str | None) -> None:
    assert slots.purpose(text) == purpose
