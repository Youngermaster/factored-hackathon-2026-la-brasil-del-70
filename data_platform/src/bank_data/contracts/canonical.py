"""Canonical codes for categorical source values.

Silver stores one code per meaning: ``Tarjeta Crédito`` and ``Credit Card`` both become ``credit_card``;
``México`` and ``Mexico`` become ``MX``. Translations live here; every other accepted value becomes its lower
snake case form (``Call Center`` to ``call_center``). ``bank-data codegen`` writes the full mapping as the
``canonical_values`` dbt seed, and the silver ``accepted_values`` tests list the canonical codes.
"""

import re

from bank_data.contracts.tables import TABLES, ColumnSpec

TRANSLATIONS: dict[str, dict[str, str]] = {
    "product_type": {
        "Checking Account": "checking_account",
        "Cuenta Corriente": "checking_account",
        "Savings Account": "savings_account",
        "Cuenta Ahorro": "savings_account",
        "Credit Card": "credit_card",
        "Tarjeta Crédito": "credit_card",
        "Debit Card": "debit_card",
        "Tarjeta Débito": "debit_card",
        "Personal Loan": "personal_loan",
        "Préstamo Personal": "personal_loan",
        "Mortgage": "mortgage",
        "Préstamo Hipotecario": "mortgage",
        "Investment": "investment",
        "Inversión": "investment",
        "Insurance": "insurance",
        "Seguro": "insurance",
    },
    "country": {
        "Mexico": "MX",
        "México": "MX",
        "Colombia": "CO",
        "Argentina": "AR",
        "USA": "US",
        "United States": "US",
        "Spain": "ES",
        "España": "ES",
        "Brazil": "BR",
        "Brasil": "BR",
    },
    "document_type": {
        "DNI": "dni",
        "CURP": "curp",
        "CC": "cc",
        "CE": "ce",
        "Passport": "passport",
        "Pasaporte": "passport",
    },
    "geographic_zone": {
        "Urban": "urban",
        "Urbana": "urban",
        "Suburban": "suburban",
        "Suburbana": "suburban",
        "Rural": "rural",
    },
    "sentiment": {
        "Very Positive": "very_positive",
        "Muy Positivo": "very_positive",
        "Positive": "positive",
        "Positivo": "positive",
        "Neutral": "neutral",
        "Negative": "negative",
        "Negativo": "negative",
        "Very Negative": "very_negative",
        "Muy Negativo": "very_negative",
    },
    "reason_category": {
        "Transactional": "transactional",
        "Transaccional": "transactional",
        "Product": "product",
        "Producto": "product",
        "Technical": "technical",
        "Técnico": "technical",
        "Commercial": "commercial",
        "Comercial": "commercial",
        "Complaint": "complaint",
        "Queja": "complaint",
        "Retention": "retention",
        "Retención": "retention",
    },
}

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


def snake(value: str) -> str:
    """The generic canonical form; the SQL ``canonical`` macro computes exactly the same thing."""
    return _NON_ALNUM.sub("_", value.strip()).strip("_").lower()


def canonical_value(domain: str, value: str) -> str:
    if domain == "identity":
        return value.strip()
    translated = TRANSLATIONS.get(domain, {}).get(value.strip())
    if translated is not None:
        return translated
    return snake(value)


def canonical_codes(column: ColumnSpec) -> tuple[str, ...]:
    """The canonical codes a column may hold in silver, in first-seen order (empty for free columns)."""
    if column.canonical is None:
        return ()
    values = column.accepted if column.accepted is not None else tuple(TRANSLATIONS.get(column.canonical, {}))
    codes: list[str] = []
    for value in values:
        code = canonical_value(column.canonical, value)
        if code not in codes:
            codes.append(code)
    return tuple(codes)


def seed_rows() -> list[tuple[str, str, str]]:
    """Every ``(domain, source_value, canonical)`` pair of the translated domains.

    ``snake`` and ``identity`` columns need no seed rows: the SQL macro computes them directly."""
    pairs: dict[tuple[str, str], str] = {}
    for domain, mapping in TRANSLATIONS.items():
        for source, code in mapping.items():
            pairs[(domain, source)] = code
    for table in TABLES:
        for column in table.columns:
            if column.canonical in (None, "identity", "snake") or column.accepted is None:
                continue
            domain = str(column.canonical)
            for value in column.accepted:
                pairs.setdefault((domain, value), canonical_value(domain, value))
    return sorted((domain, source, code) for (domain, source), code in pairs.items())
