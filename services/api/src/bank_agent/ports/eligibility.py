"""Eligibility policy port: the synthetic eligibility service (phase 06 implements it over ``ELG`` rules)."""

from typing import Annotated, Protocol, Self

from pydantic import model_validator

from bank_agent.domain.base import Code, DomainModel, Internal, Pii, UtcDatetime
from bank_agent.domain.credit import CreditProduct, CreditProfile, TermMonths
from bank_agent.domain.eligibility import EligibilityAssessment, RiskEstimate
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Money


class CreditApplicationFacts(DomainModel):
    """What the customer asked for in this conversation. Declared income is the customer's own statement."""

    requested_amount: Money
    requested_term_months: TermMonths
    purpose: Code
    declared_monthly_income: Annotated[Money | None, Pii("financial")] = None


class EligibilityRequest(DomainModel):
    """Everything the eligibility service may use. The profile and the estimate are internal inputs.

    ``profile`` is ``None`` when the customer has no credit profile; ``risk_estimate`` is ``None`` when the
    estimator was unavailable. ``jurisdiction`` comes from the verified customer profile, never from text.
    """

    product: CreditProduct
    profile: Annotated[CreditProfile | None, Internal()] = None
    application: CreditApplicationFacts
    risk_estimate: Annotated[RiskEstimate | None, Internal()] = None
    jurisdiction: Country
    as_of: UtcDatetime

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.product.jurisdiction is not self.jurisdiction:
            raise ValueError("the product must belong to the customer's jurisdiction")
        amounts = (self.application.requested_amount, self.application.declared_monthly_income)
        if any(amount is not None and amount.currency is not self.product.currency for amount in amounts):
            raise ValueError("requested and declared amounts must be in the product currency")
        return self


class EligibilityPolicy(Protocol):
    """The synthetic eligibility service: an indicative outcome from team-authored, synthetic ``ELG`` rules.

    Preconditions: the request was built by the workflow engine from the catalog, the verified customer's
    profile, the conversation's application facts, and the risk estimator's output; no model output selects
    this port.
    Postconditions: deterministic for the same request and policy pack, with no I/O at call time (the
    assessment id and time come from the injected ``IdGenerator`` and ``Clock``). The result
    names every rule it evaluated with versions and clause references, identifies the service with a
    ``ServiceRef`` (``eligibility:synthetic@<pack version>``), and is labeled synthetic. There is no approved
    outcome. Missing inputs produce ``insufficient_data`` or ``review_required`` with the missing facts, never
    an exception and never ``indicatively_eligible``. A missing risk estimate, or one with band ``unknown``,
    produces ``review_required`` with ``risk_estimate_unavailable``. A product without self-service
    eligibility (a mortgage) produces ``review_required`` with ``product_requires_human_assessment``.
    Errors: ``EligibilityServiceUnavailableError`` only when the service itself cannot run (for example a
    policy pack that failed to load); ordinary input never raises.
    Isolation: works only on the request it is given, never fetches data, and never returns the profile or the
    estimate to the caller in a customer-facing form (``EligibilityView`` carries neither).
    """

    def assess(self, request: EligibilityRequest) -> EligibilityAssessment:
        """Return the assessment for ``request``."""
        ...
