"""Deterministic slot extraction for account inquiries and credit requests, the fallback when the language model is
off or fails (and the tie-breaker for amounts, terms, and income, which are always normalized here).

It reads only what the customer wrote: a product type, a card or account ending, a requested amount, a term in
months or years, a monthly income the customer declares ("gano 30 mil al mes", "minha renda é de 5 mil"), and a
purpose mapped to the catalog's codes. An unknown slot stays ``None``; nothing is estimated or completed.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from bank_agent.application.understanding import amounts
from bank_agent.application.understanding.text import fold
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.product import ProductType

_ACCOUNT_TYPES: tuple[tuple[ProductType, str], ...] = (
    (ProductType.SAVINGS_ACCOUNT, r"ahorro|poupanca|savings"),
    (ProductType.CHECKING_ACCOUNT, r"cuenta corriente|conta corrente|cheques|checking"),
    (ProductType.CREDIT_CARD, r"(tarjeta|cartao) de credito|credit card"),
    (ProductType.DEBIT_CARD, r"(tarjeta|cartao) de debito|debit card"),
    (ProductType.PERSONAL_LOAN, r"prestamo|emprestimo|loan"),
    (ProductType.MORTGAGE, r"hipoteca|financiamento imobiliario|mortgage"),
)
_CREDIT_TYPES: tuple[tuple[CreditProductType, str], ...] = (
    (CreditProductType.MORTGAGE, r"hipoteca|hipotecario|imobiliario|vivienda|casa propia|imovel|mortgage"),
    (CreditProductType.CREDIT_CARD, r"tarjeta|cartao|credit card|\bcard\b"),
    (CreditProductType.PERSONAL_LOAN, r"prestamo|emprestimo|credito personal|credito pessoal|\bloan\b"),
)
_PURPOSES: tuple[tuple[str, str], ...] = (
    ("debt_consolidation", r"consolid|(pagar|juntar|unificar|quitar) (mis |otras |minhas |as )?(deudas|dividas)"),
    ("home_improvement", r"remodel|reform|arreglar (la |mi )?casa|mejoras? (del |en el |de la )?(hogar|casa)|obras"),
    ("education", r"estudi|educaci|educacao|universidad|faculdade|maestria|mestrado|curso|colegiatura"),
)
_WORD_NUMBERS = {"un": 1, "una": 1, "um": 1, "uma": 1, "dos": 2, "dois": 2, "duas": 2, "tres": 3, "cuatro": 4,
                 "quatro": 4, "cinco": 5, "seis": 6, "diez": 10, "dez": 10}  # fmt: skip
_TERM = re.compile(r"\b(?P<n>\d{1,3}|[a-z]+)\s(?P<unit>meses|mes|months?|anos?|years?)\b")
_INCOME = re.compile(
    r"\b(gano|ganho|cobro|recibo|mi (ingreso|sueldo|salario)|mis ingresos|meu (salario|rendimento)|minha renda|"
    r"renda (mensal )?(e )?de|ingreso (mensual )?(es )?de|my (monthly )?income|i earn)\b"
)


def _first[T](table: tuple[tuple[T, str], ...], folded: str) -> T | None:
    return next((value for value, pattern in table if re.search(pattern, folded)), None)


def account_product_type(text: str) -> ProductType | None:
    return _first(_ACCOUNT_TYPES, fold(text))


def credit_product_type(text: str) -> CreditProductType | None:
    return _first(_CREDIT_TYPES, fold(text))


def purpose(text: str) -> str | None:
    return _first(_PURPOSES, fold(text))


def term_months(text: str) -> int | None:
    """A term in months ("24 meses", "dos años" is 24); ``None`` when the text names none."""
    match = _TERM.search(fold(text))
    if match is None:
        return None
    raw = match["n"]
    count = int(raw) if raw.isdigit() else _WORD_NUMBERS.get(raw)
    if not count:
        return None
    return count * 12 if match["unit"].startswith(("ano", "year")) else count


@dataclass(frozen=True)
class CreditAmounts:
    requested: amounts.AmountMention | None
    income: amounts.AmountMention | None


def credit_amounts(text: str) -> CreditAmounts:
    """The requested amount (before any income phrase) and a declared monthly income (after it)."""
    folded = fold(text)
    match = _INCOME.search(folded)
    if match is None:
        return CreditAmounts(amounts.best_amount(text), None)
    before, after = folded[: match.start()], folded[match.end() :]
    return CreditAmounts(amounts.best_amount(before), amounts.best_amount(after))


def positive(value: Decimal | None) -> Decimal | None:
    return value if value is not None and value > 0 else None
