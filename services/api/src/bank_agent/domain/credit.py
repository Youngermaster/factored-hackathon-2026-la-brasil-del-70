"""Credit products, the customer's credit profile, and credit application intakes.

Everything here supports information and eligibility *support*, never a lending decision:

- ``CreditProduct`` is an entry of the synthetic catalog (public information, labeled synthetic). Phase 06
  authors the content under ``policies/credit/``.
- ``CreditProfile`` holds the credit facts of one customer. The score, income, days past due, and utilization
  are internal: never shown to customers and never sent to a model. A missing fact stays ``None`` and is never
  imputed here; the synthetic eligibility service turns it into a review path.
- ``CreditApplicationIntake`` records an application for human review. Its statuses have no approved or
  declined value by design: a reviewer outside the prototype would decide.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, NonNegativeInt, StringConstraints, model_validator

from bank_agent.domain.base import Code, DomainModel, Internal, Pii, UtcDatetime
from bank_agent.domain.decision import ClauseId
from bank_agent.domain.errors import InvalidApplicationTransitionError
from bank_agent.domain.identifiers import (
    ApplicationId,
    AssessmentId,
    ConversationId,
    CreditProductCode,
    CustomerId,
    IdempotencyKey,
)
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Amount, Currency, Money
from bank_agent.domain.product import MAX_ANNUAL_RATE

MAX_TERM_MONTHS = 480
TermMonths = Annotated[int, Field(ge=1, le=MAX_TERM_MONTHS)]
AnnualRate = Annotated[Amount, Field(ge=0, le=MAX_ANNUAL_RATE)]
CreditScore = Annotated[int, Field(ge=300, le=850)]


class CreditProductType(StrEnum):
    CREDIT_CARD = "credit_card"
    PERSONAL_LOAN = "personal_loan"
    MORTGAGE = "mortgage"


class CreditProduct(DomainModel):
    """One synthetic catalog entry. Indicative ranges only: never an offer.

    ``self_service_eligibility`` is false for products whose eligibility needs facts the data does not have
    (a mortgage needs collateral facts); the eligibility service then returns ``review_required``.
    """

    product_code: CreditProductCode
    product_type: CreditProductType
    jurisdiction: Country
    currency: Currency
    min_amount: Money
    max_amount: Money
    min_term_months: TermMonths
    max_term_months: TermMonths
    min_annual_rate: AnnualRate
    max_annual_rate: AnnualRate
    purposes: Annotated[tuple[Code, ...], Field(min_length=1)]
    required_information: tuple[Code, ...] = ()
    eligibility_clause_ids: tuple[ClauseId, ...] = ()
    self_service_eligibility: bool
    catalog_version: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    synthetic: Literal[True]

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.min_amount.currency is not self.currency or self.max_amount.currency is not self.currency:
            raise ValueError("catalog amounts must be in the product currency")
        if not Money.zero(self.currency) < self.min_amount <= self.max_amount:
            raise ValueError("the amount range must be positive and ordered")
        if self.min_term_months > self.max_term_months or self.min_annual_rate > self.max_annual_rate:
            raise ValueError("the term and rate ranges must be ordered")
        if len(set(self.purposes)) != len(self.purposes):
            raise ValueError("purposes must not repeat")
        for clause_id in self.eligibility_clause_ids:
            family, jurisdiction, _ = clause_id.split("-", 2)
            if family != "ELG" or jurisdiction not in (self.jurisdiction.value, "ALL"):
                raise ValueError("eligibility clauses must be ELG clauses of the product jurisdiction or ALL")
        if self.product_type is CreditProductType.MORTGAGE and self.self_service_eligibility:
            raise ValueError("mortgage eligibility always needs a human assessment")
        return self

    def allows_purpose(self, purpose: str) -> bool:
        return purpose in self.purposes


class CreditProfile(DomainModel):
    """The credit facts of one customer, derived from the core banking data (phase 03).

    ``total_credit_limit`` is set only when every credit product shares one currency. ``utilization`` may
    exceed 1 when a limit is exceeded.
    """

    customer_id: CustomerId
    credit_score: Annotated[CreditScore | None, Internal()] = None
    estimated_monthly_income: Annotated[Money | None, Internal()] = None
    tenure_months: NonNegativeInt | None = None
    credit_product_count: NonNegativeInt | None = None
    max_days_past_due: Annotated[NonNegativeInt | None, Internal()] = None
    total_credit_limit: Money | None = None
    utilization: Annotated[Annotated[Amount, Field(ge=0)] | None, Internal()] = None
    as_of: date

    @model_validator(mode="after")
    def _validate(self) -> Self:
        for amount in (self.estimated_monthly_income, self.total_credit_limit):
            if amount is not None and amount.amount < 0:
                raise ValueError("income and credit limits cannot be negative")
        return self

    def missing_facts(self) -> tuple[str, ...]:
        """Names of the facts that are unknown, in field order. Used as ``missing_facts`` codes."""
        facts = ("credit_score", "estimated_monthly_income", "tenure_months", "max_days_past_due")
        return tuple(name for name in facts if getattr(self, name) is None)


class ApplicationStatus(StrEnum):
    SUBMITTED = "submitted"
    UNDER_HUMAN_REVIEW = "under_human_review"
    WITHDRAWN = "withdrawn"
    CLOSED = "closed"


APPLICATION_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.SUBMITTED: frozenset({ApplicationStatus.UNDER_HUMAN_REVIEW, ApplicationStatus.WITHDRAWN}),
    ApplicationStatus.UNDER_HUMAN_REVIEW: frozenset({ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED}),
    ApplicationStatus.WITHDRAWN: frozenset(),
    ApplicationStatus.CLOSED: frozenset(),
}
TERMINAL_APPLICATION_STATUSES = frozenset(status for status, targets in APPLICATION_TRANSITIONS.items() if not targets)
CUSTOMER_APPLICATION_TRANSITIONS = frozenset({ApplicationStatus.WITHDRAWN})
"""The only move a customer makes; reviewers (phase 16) move applications to review and close them."""
REVIEWABLE_APPLICATION_STATUSES = frozenset({ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_HUMAN_REVIEW})
"""Statuses that make an intake a review item of its own: agents read these without a handoff (ADR 0021)."""


class ApplicationStatusChange(DomainModel):
    from_status: ApplicationStatus
    to_status: ApplicationStatus
    at: UtcDatetime
    reason_code: Code


class CreditApplicationIntake(DomainModel):
    """An application recorded for human review. It never decides and never moves money.

    ``declared_monthly_income`` is what the customer said, kept apart from the profile's estimated income.
    """

    application_id: ApplicationId
    customer_id: CustomerId
    product_code: CreditProductCode
    requested_amount: Money
    requested_term_months: TermMonths
    purpose: Code
    declared_monthly_income: Annotated[Money | None, Pii("financial")] = None
    assessment_ref: AssessmentId | None = None
    idempotency_key: IdempotencyKey
    status: ApplicationStatus
    created_at: UtcDatetime
    updated_at: UtcDatetime
    status_history: tuple[ApplicationStatusChange, ...] = ()
    origin_conversation_id: ConversationId | None = None
    version: NonNegativeInt = 0
    synthetic_policy: Literal[True] = True

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.requested_amount.amount <= 0:
            raise ValueError("the requested amount must be positive")
        income = self.declared_monthly_income
        if income is not None and (income.amount < 0 or income.currency is not self.requested_amount.currency):
            raise ValueError("declared income must be non-negative and in the requested currency")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        return self

    @classmethod
    def submit(
        cls,
        *,
        application_id: ApplicationId,
        customer_id: CustomerId,
        product_code: CreditProductCode,
        requested_amount: Money,
        requested_term_months: int,
        purpose: str,
        idempotency_key: IdempotencyKey,
        created_at: datetime,
        declared_monthly_income: Money | None = None,
        assessment_ref: AssessmentId | None = None,
        origin_conversation_id: ConversationId | None = None,
    ) -> Self:
        return cls(
            application_id=application_id,
            customer_id=customer_id,
            product_code=product_code,
            requested_amount=requested_amount,
            requested_term_months=requested_term_months,
            purpose=purpose,
            declared_monthly_income=declared_monthly_income,
            assessment_ref=assessment_ref,
            idempotency_key=idempotency_key,
            status=ApplicationStatus.SUBMITTED,
            created_at=created_at,
            updated_at=created_at,
            origin_conversation_id=origin_conversation_id,
        )

    @property
    def is_open(self) -> bool:
        return self.status not in TERMINAL_APPLICATION_STATUSES

    def same_request(self, other: "CreditApplicationIntake") -> bool:
        """True when ``other`` asks for the same thing (idempotent replay of the same intake)."""
        fields = ("product_code", "requested_amount", "requested_term_months", "purpose", "declared_monthly_income")
        return all(getattr(self, name) == getattr(other, name) for name in fields)

    def transition_to(self, status: ApplicationStatus, *, at: datetime, reason_code: str) -> Self:
        """Move to ``status``, recording the change. Illegal moves raise ``InvalidApplicationTransitionError``."""
        if status not in APPLICATION_TRANSITIONS[self.status]:
            raise InvalidApplicationTransitionError(f"an application cannot move from {self.status} to {status}")
        change = ApplicationStatusChange(from_status=self.status, to_status=status, at=at, reason_code=reason_code)
        if change.at < self.updated_at:
            raise InvalidApplicationTransitionError("a status change cannot precede the last update")
        return self.evolve(status=status, updated_at=change.at, status_history=(*self.status_history, change))
