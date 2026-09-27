import inspect
from datetime import date

import pytest
from pydantic import ValidationError

from bank_agent.domain.base import internal_fields
from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.identifiers import CustomerId
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import WorkflowId
from bank_agent.ports.eligibility import CreditApplicationFacts, EligibilityRequest
from bank_agent.ports.policy import PolicyRepository
from bank_agent_builders import CUSTOMER_A, T0, risk_estimate
from bank_agent_credit import catalog_products


def facts(amount: str = "40000", currency: Currency = Currency.MXN) -> CreditApplicationFacts:
    return CreditApplicationFacts(
        requested_amount=Money.of(amount, currency), requested_term_months=24, purpose="debt_consolidation"
    )


def test_an_eligibility_request_keeps_the_profile_and_estimate_internal() -> None:
    request = EligibilityRequest(
        product=catalog_products()[0],
        profile=CreditProfile(customer_id=CustomerId(CUSTOMER_A), credit_score=700, as_of=date(2026, 6, 1)),
        application=facts(),
        risk_estimate=risk_estimate(),
        jurisdiction=Country.MX,
        as_of=T0,
    )
    assert {"profile", "risk_estimate"} <= internal_fields(EligibilityRequest)
    assert request.risk_estimate is not None


def test_an_eligibility_request_stays_in_the_customer_jurisdiction_and_currency() -> None:
    with pytest.raises(ValidationError, match="jurisdiction"):
        EligibilityRequest(product=catalog_products()[0], application=facts(), jurisdiction=Country.CO, as_of=T0)
    with pytest.raises(ValidationError, match="product currency"):
        EligibilityRequest(
            product=catalog_products()[0], application=facts(currency=Currency.USD), jurisdiction=Country.MX, as_of=T0
        )


def test_bound_policy_lookup_names_the_workflow() -> None:
    parameters = inspect.signature(PolicyRepository.get_bound).parameters
    assert list(parameters) == ["self", "workflow", "state", "jurisdiction", "language"]
    assert parameters["workflow"].annotation is WorkflowId
