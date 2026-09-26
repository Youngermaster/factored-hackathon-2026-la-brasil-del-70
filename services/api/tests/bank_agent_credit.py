"""Synthetic credit fixtures shared by tests: catalog entries and credit profiles.

Every value is invented by the team and labeled as a fixture. The real synthetic catalog is authored in
phase 06 under ``policies/credit/``.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from bank_agent.domain.credit import CreditProduct, CreditProductType, CreditProfile
from bank_agent.domain.identifiers import CustomerId
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Currency, Money
from bank_agent_builders import CUSTOMER_A, CUSTOMER_B

CATALOG_VERSION = "catalog-fixture-1"


def credit_product(
    code: str,
    product_type: CreditProductType,
    country: Country,
    min_amount: str,
    max_amount: str,
    **overrides: Any,
) -> CreditProduct:
    currency = country.default_currency
    fields: dict[str, Any] = {
        "product_code": code,
        "product_type": product_type,
        "jurisdiction": country,
        "currency": currency,
        "min_amount": Money.of(min_amount, currency),
        "max_amount": Money.of(max_amount, currency),
        "min_term_months": 6 if product_type is not CreditProductType.MORTGAGE else 60,
        "max_term_months": 48 if product_type is not CreditProductType.MORTGAGE else 240,
        "min_annual_rate": Decimal("20.00"),
        "max_annual_rate": Decimal("70.00"),
        "purposes": ["general_purpose"] if product_type is not CreditProductType.MORTGAGE else ["home_purchase"],
        "required_information": ["declared_monthly_income"],
        "eligibility_clause_ids": [f"ELG-{country.value}-1.1", "ELG-ALL-1"],
        "self_service_eligibility": product_type is not CreditProductType.MORTGAGE,
        "catalog_version": CATALOG_VERSION,
        "synthetic": True,
    }
    return CreditProduct.model_validate({**fields, **overrides})


def catalog_products() -> tuple[CreditProduct, ...]:
    """Two fixture products per jurisdiction: a card and a loan for MX and AR, a card and a mortgage for CO."""
    return (
        credit_product("MX-CC-FIXTURE", CreditProductType.CREDIT_CARD, Country.MX, "5000", "80000"),
        credit_product("MX-PL-FIXTURE", CreditProductType.PERSONAL_LOAN, Country.MX, "10000", "300000"),
        credit_product("CO-CC-FIXTURE", CreditProductType.CREDIT_CARD, Country.CO, "1000000", "20000000"),
        credit_product("CO-MG-FIXTURE", CreditProductType.MORTGAGE, Country.CO, "80000000", "900000000"),
        credit_product("AR-CC-FIXTURE", CreditProductType.CREDIT_CARD, Country.AR, "100000", "5000000"),
        credit_product("AR-PL-FIXTURE", CreditProductType.PERSONAL_LOAN, Country.AR, "200000", "20000000"),
    )


def credit_profiles() -> tuple[CreditProfile, ...]:
    """Customer A has a complete profile; customer B has no income on file."""
    return (
        CreditProfile(
            customer_id=CustomerId(CUSTOMER_A),
            credit_score=712,
            estimated_monthly_income=Money.of("32000.00", Currency.MXN),
            tenure_months=52,
            credit_product_count=1,
            max_days_past_due=0,
            total_credit_limit=Money.of("20000.00", Currency.MXN),
            utilization=Decimal("0.4225"),
            as_of=date(2026, 5, 31),
        ),
        CreditProfile(
            customer_id=CustomerId(CUSTOMER_B),
            credit_score=655,
            tenure_months=18,
            credit_product_count=1,
            max_days_past_due=0,
            as_of=date(2026, 5, 31),
        ),
    )
