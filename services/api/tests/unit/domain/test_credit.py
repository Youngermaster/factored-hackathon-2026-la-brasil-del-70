from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from bank_agent.domain.base import internal_fields, pii_fields
from bank_agent.domain.credit import (
    APPLICATION_TRANSITIONS,
    CUSTOMER_APPLICATION_TRANSITIONS,
    TERMINAL_APPLICATION_STATUSES,
    ApplicationStatus,
    CreditApplicationIntake,
    CreditProduct,
    CreditProductType,
    CreditProfile,
)
from bank_agent.domain.errors import InvalidApplicationTransitionError
from bank_agent.domain.identifiers import ApplicationId, CreditProductCode, CustomerId, IdempotencyKey
from bank_agent.domain.money import Currency, Money
from bank_agent_builders import CUSTOMER_A, T0

MXN = Currency.MXN


def mxn(amount: str) -> Money:
    return Money.of(amount, MXN)


def catalog_product(**overrides: Any) -> CreditProduct:
    fields: dict[str, Any] = {
        "product_code": "MX-PL-FIXTURE",
        "product_type": CreditProductType.PERSONAL_LOAN,
        "jurisdiction": "MX",
        "currency": MXN,
        "min_amount": mxn("5000"),
        "max_amount": mxn("150000"),
        "min_term_months": 6,
        "max_term_months": 48,
        "min_annual_rate": Decimal("28.00"),
        "max_annual_rate": Decimal("65.00"),
        "purposes": ["debt_consolidation", "home_improvement"],
        "required_information": ["declared_monthly_income"],
        "eligibility_clause_ids": ["ELG-MX-1.1", "ELG-ALL-1"],
        "self_service_eligibility": True,
        "catalog_version": "catalog-fixture-1",
        "synthetic": True,
    }
    return CreditProduct.model_validate({**fields, **overrides})


def intake(**overrides: Any) -> CreditApplicationIntake:
    fields: dict[str, Any] = {
        "application_id": ApplicationId("app-000001"),
        "customer_id": CustomerId(CUSTOMER_A),
        "product_code": CreditProductCode("MX-PL-FIXTURE"),
        "requested_amount": mxn("40000"),
        "requested_term_months": 24,
        "purpose": "debt_consolidation",
        "idempotency_key": IdempotencyKey("idem-key-fixture-app1"),
        "created_at": T0,
    }
    return CreditApplicationIntake.submit(**{**fields, **overrides})


# --- Catalog -------------------------------------------------------------------------------------------------


def test_builds_a_synthetic_catalog_entry() -> None:
    product = catalog_product()
    assert product.synthetic is True
    assert product.allows_purpose("home_improvement")
    assert not product.allows_purpose("travel")


def test_catalog_entries_must_be_labeled_synthetic() -> None:
    with pytest.raises(ValidationError):
        catalog_product(synthetic=False)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"max_amount": Money.of("1000", Currency.USD)}, "product currency"),
        ({"min_amount": mxn("200000")}, "positive and ordered"),
        ({"min_amount": mxn("0")}, "positive and ordered"),
        ({"min_term_months": 60}, "ordered"),
        ({"max_annual_rate": Decimal("10.00")}, "ordered"),
        ({"purposes": ["travel", "travel"]}, "must not repeat"),
        ({"eligibility_clause_ids": ["CRE-MX-1"]}, "ELG clauses"),
        ({"eligibility_clause_ids": ["ELG-CO-1"]}, "ELG clauses"),
    ],
)
def test_rejects_inconsistent_catalog_entries(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        catalog_product(**overrides)


def test_mortgage_eligibility_is_never_self_service() -> None:
    with pytest.raises(ValidationError, match="human assessment"):
        catalog_product(product_type=CreditProductType.MORTGAGE)
    mortgage = catalog_product(product_type=CreditProductType.MORTGAGE, self_service_eligibility=False)
    assert not mortgage.self_service_eligibility


def test_terms_are_bounded() -> None:
    with pytest.raises(ValidationError):
        catalog_product(max_term_months=481)


# --- Profile -------------------------------------------------------------------------------------------------


def test_profile_marks_the_sensitive_credit_facts_internal() -> None:
    assert internal_fields(CreditProfile) == frozenset(
        {"credit_score", "estimated_monthly_income", "max_days_past_due", "utilization"}
    )
    assert pii_fields(CreditProfile) == {}


def test_profile_facts_stay_missing_and_are_reported() -> None:
    profile = CreditProfile(customer_id=CustomerId(CUSTOMER_A), tenure_months=40, as_of=date(2026, 6, 1))
    assert profile.credit_score is None
    assert profile.missing_facts() == ("credit_score", "estimated_monthly_income", "max_days_past_due")


def test_profile_validates_ranges() -> None:
    with pytest.raises(ValidationError):
        CreditProfile(customer_id=CustomerId(CUSTOMER_A), credit_score=250, as_of=date(2026, 6, 1))
    with pytest.raises(ValidationError, match="negative"):
        CreditProfile(customer_id=CustomerId(CUSTOMER_A), estimated_monthly_income=mxn("-1"), as_of=date(2026, 6, 1))
    with pytest.raises(ValidationError):
        CreditProfile(customer_id=CustomerId(CUSTOMER_A), utilization=Decimal("-0.1"), as_of=date(2026, 6, 1))
    over = CreditProfile(customer_id=CustomerId(CUSTOMER_A), utilization=Decimal("1.25"), as_of=date(2026, 6, 1))
    assert over.utilization == Decimal("1.25")


# --- Application intake --------------------------------------------------------------------------------------


def test_submits_an_intake_for_human_review() -> None:
    application = intake(declared_monthly_income=mxn("30000"))
    assert application.status is ApplicationStatus.SUBMITTED
    assert application.synthetic_policy is True
    assert application.is_open
    assert pii_fields(CreditApplicationIntake) == {"declared_monthly_income": "financial"}


def test_intake_validates_amounts() -> None:
    with pytest.raises(ValidationError, match="positive"):
        intake(requested_amount=mxn("0"))
    with pytest.raises(ValidationError, match="declared income"):
        intake(declared_monthly_income=Money.of("1000", Currency.USD))
    with pytest.raises(ValidationError):
        intake(requested_term_months=0)


def test_same_request_ignores_ids_and_status() -> None:
    first = intake()
    replay = intake(application_id=ApplicationId("app-000002"), created_at=T0 + timedelta(minutes=1))
    assert first.same_request(replay)
    assert not first.same_request(intake(requested_amount=mxn("40001")))


ALL_PAIRS = [(source, target) for source in ApplicationStatus for target in ApplicationStatus]


@pytest.mark.parametrize(("source", "target"), ALL_PAIRS, ids=lambda s: s.value)
def test_application_lifecycle_table(source: ApplicationStatus, target: ApplicationStatus) -> None:
    application = intake().evolve(status=source)
    allowed = target in APPLICATION_TRANSITIONS[source]
    if allowed:
        moved = application.transition_to(target, at=T0 + timedelta(hours=1), reason_code="fixture")
        assert moved.status is target
        assert moved.status_history[-1].from_status is source
    else:
        with pytest.raises(InvalidApplicationTransitionError):
            application.transition_to(target, at=T0 + timedelta(hours=1), reason_code="fixture")


def test_lifecycle_has_no_decision_status_and_two_terminal_states() -> None:
    assert {ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED} == TERMINAL_APPLICATION_STATUSES
    assert {ApplicationStatus.WITHDRAWN} == CUSTOMER_APPLICATION_TRANSITIONS


def test_a_change_cannot_precede_the_last_update() -> None:
    with pytest.raises(InvalidApplicationTransitionError, match="precede"):
        intake().transition_to(ApplicationStatus.WITHDRAWN, at=T0 - timedelta(seconds=1), reason_code="fixture")


@given(st.lists(st.sampled_from(list(ApplicationStatus)), max_size=8))
def test_random_transitions_never_leave_a_terminal_state(targets: list[ApplicationStatus]) -> None:
    application = intake()
    at = T0
    for target in targets:
        at += timedelta(minutes=1)
        was_terminal = not application.is_open
        try:
            application = application.transition_to(target, at=at, reason_code="fixture")
        except InvalidApplicationTransitionError:
            continue
        assert not was_terminal
