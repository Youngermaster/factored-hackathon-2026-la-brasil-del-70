"""Predictive risk estimates and the synthetic eligibility service's assessments, kept apart.

The brief requires three separate components for credit: conversation handling, predictive risk estimates,
and eligibility policy. This module holds what the last two exchange:

- ``CreditRiskFeatures`` is an explicit allowlist of model inputs. It has no identifier, no free text, and no
  protected or proxy attribute (gender, birth date or age, marital status, accent, location below country,
  segment, occupation, education level), so those are excluded by construction.
- ``RiskEstimate`` is a probability with an interval, a band, and quality flags, produced by the
  ``RiskEstimator`` port. It is internal: never shown to customers, never sent to a model, and never a decision.
- ``EligibilityAssessment`` is the output of the ``EligibilityPolicy`` port: an outcome backed by ``ELG`` rule
  results. No outcome means approved; the service is synthetic and labeled so everywhere.
- ``EligibilityView`` is the only part a customer sees: outcome, reasons, an uncertainty statement, the review
  path, and the disclaimer. It has no field for the estimate or the profile.
"""

import re
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    Field,
    GetJsonSchemaHandler,
    NonNegativeInt,
    StringConstraints,
    model_serializer,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from bank_agent.domain.base import Code, DomainModel, Internal, UtcDatetime
from bank_agent.domain.credit import CreditProductType, CreditScore, TermMonths
from bank_agent.domain.decision import ClauseRef, RuleId, RuleResult
from bank_agent.domain.identifiers import ApplicationId, AssessmentId, CreditProductCode, RiskEstimateId
from bank_agent.domain.intelligence import ModelComponent, ModelRef
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Amount

Ratio = Annotated[Amount, Field(ge=0)]
UnitInterval = Annotated[Amount, Field(ge=0, le=1)]
ELIGIBILITY_RULE_PREFIX = "ELG."


# --- Risk estimates ------------------------------------------------------------------------------------------


class CreditRiskFeatures(DomainModel):
    """The only inputs a risk estimator receives. Income is normalized to USD by the application."""

    jurisdiction: Country
    product_type: CreditProductType
    requested_term_months: TermMonths
    credit_score: CreditScore | None = None
    monthly_income_usd: Ratio | None = None
    tenure_months: NonNegativeInt | None = None
    credit_product_count: NonNegativeInt | None = None
    max_days_past_due: NonNegativeInt | None = None
    utilization: Ratio | None = None
    requested_amount_to_income: Ratio | None = None

    def missing(self) -> tuple[str, ...]:
        """Names of the optional features that are unknown, in field order."""
        return tuple(name for name, value in self if value is None)


class RiskBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class UncertaintyFlag(StrEnum):
    MISSING_FEATURES = "missing_features"
    OUT_OF_DISTRIBUTION = "out_of_distribution"
    WIDE_INTERVAL = "wide_interval"
    MODEL_UNAVAILABLE = "model_unavailable"
    """Set by a fallback decorator when the primary model failed and a baseline produced the estimate."""


_UNKNOWN_BAND_FLAGS = frozenset(
    {UncertaintyFlag.MISSING_FEATURES, UncertaintyFlag.OUT_OF_DISTRIBUTION, UncertaintyFlag.MODEL_UNAVAILABLE}
)


def _check_interval(low: Decimal, probability: Decimal, high: Decimal) -> None:
    if not low <= probability <= high:
        raise ValueError("the interval must satisfy low <= probability <= high")


def _check_flags(band: RiskBand, flags: tuple[UncertaintyFlag, ...]) -> None:
    if len(set(flags)) != len(flags):
        raise ValueError("uncertainty flags must not repeat")
    if band is RiskBand.UNKNOWN and not _UNKNOWN_BAND_FLAGS & set(flags):
        raise ValueError("an unknown band needs a missing-features, out-of-distribution, or model-unavailable flag")


def _check_estimator(model: ModelRef) -> None:
    if model.component is not ModelComponent.RISK_ESTIMATOR:
        raise ValueError("a risk estimate comes from a risk_estimator model")


class RiskEstimateRef(DomainModel):
    """Which estimate an assessment used: the model at its concrete version and the estimate id."""

    model: ModelRef
    estimate_id: RiskEstimateId


class RiskEstimate(DomainModel):
    """The estimated probability of the documented adverse outcome (``label_definition``, phase 10).

    Trained on synthetic organizer data (``synthetic_data``). Internal: one input to the eligibility service.
    """

    estimate_id: RiskEstimateId
    model: ModelRef
    probability: Annotated[UnitInterval, Internal()]
    interval_low: Annotated[UnitInterval, Internal()]
    interval_high: Annotated[UnitInterval, Internal()]
    band: Annotated[RiskBand, Internal()]
    flags: tuple[UncertaintyFlag, ...] = ()
    label_definition: Code
    calibrated: bool
    computed_at: UtcDatetime
    synthetic_data: Literal[True] = True

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _check_estimator(self.model)
        _check_interval(self.interval_low, self.probability, self.interval_high)
        _check_flags(self.band, self.flags)
        return self

    @property
    def ref(self) -> RiskEstimateRef:
        return RiskEstimateRef(model=self.model, estimate_id=self.estimate_id)


# --- Eligibility ---------------------------------------------------------------------------------------------


class EligibilityOutcome(StrEnum):
    """There is no approved outcome by design: the synthetic service gives an indication, never a decision."""

    INDICATIVELY_ELIGIBLE = "indicatively_eligible"
    NOT_ELIGIBLE = "not_eligible"
    REVIEW_REQUIRED = "review_required"
    INSUFFICIENT_DATA = "insufficient_data"


REVIEW_OUTCOMES = frozenset({EligibilityOutcome.REVIEW_REQUIRED, EligibilityOutcome.INSUFFICIENT_DATA})


class ReviewReason(StrEnum):
    MISSING_INCOME = "missing_income"
    MISSING_CREDIT_SCORE = "missing_credit_score"
    BORDERLINE_RISK_INTERVAL = "borderline_risk_interval"
    RISK_ESTIMATE_UNAVAILABLE = "risk_estimate_unavailable"
    DAYS_PAST_DUE_PRESENT = "days_past_due_present"
    AMOUNT_ABOVE_REVIEW_THRESHOLD = "amount_above_review_threshold"
    CUSTOMER_CONTESTS_RESULT = "customer_contests_result"
    PRODUCT_REQUIRES_HUMAN_ASSESSMENT = "product_requires_human_assessment"
    """The product needs facts the data does not have, such as collateral for a mortgage."""


_NAME = r"[a-z][a-z0-9_]{0,63}"
_VERSION = r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
SERVICE_REF_PATTERN = rf"^eligibility:{_NAME}@{_VERSION}$"


class ServiceRef(DomainModel):
    """The eligibility service at a policy pack version, serialized as ``eligibility:synthetic@<pack>``.

    A separate type from ``ModelRef``, so a record can never confuse a model with the policy service.
    """

    name: Annotated[str, StringConstraints(pattern=rf"^{_NAME}$")]
    version: Annotated[str, StringConstraints(pattern=rf"^{_VERSION}$")]

    @model_validator(mode="before")
    @classmethod
    def _parse_string(cls, value: object) -> object:
        if isinstance(value, str):
            match = re.fullmatch(r"eligibility:([^@]+)@(.+)", value)
            if match is None:
                raise ValueError("a service reference has the form eligibility:name@version")
            return {"name": match[1], "version": match[2]}
        return value

    @model_serializer(mode="plain", when_used="always")
    def _serialize(self) -> str:
        return str(self)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler, /) -> JsonSchemaValue:
        return {"type": "string", "pattern": SERVICE_REF_PATTERN, "title": "ServiceRef"}

    def __str__(self) -> str:
        return f"eligibility:{self.name}@{self.version}"


class EligibilityAssessment(DomainModel):
    """The synthetic eligibility service's result for one product and one request."""

    assessment_id: AssessmentId
    product_code: CreditProductCode
    outcome: EligibilityOutcome
    rule_results: tuple[RuleResult, ...]
    review_reasons: tuple[ReviewReason, ...] = ()
    missing_facts: tuple[Code, ...] = ()
    risk_estimate_ref: RiskEstimateRef | None = None
    policy_pack_version: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    service: ServiceRef
    synthetic: Literal[True] = True
    evaluated_at: UtcDatetime

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if any(not result.rule_id.startswith(ELIGIBILITY_RULE_PREFIX) for result in self.rule_results):
            raise ValueError("an eligibility assessment uses ELG rules only")
        if len(set(self.review_reasons)) != len(self.review_reasons):
            raise ValueError("review reasons must not repeat")
        rule_missing = {fact for result in self.rule_results for fact in result.missing_facts}
        if not rule_missing <= set(self.missing_facts):
            raise ValueError("missing_facts must include every rule result's missing facts")
        if self.outcome in REVIEW_OUTCOMES and not (self.review_reasons or self.missing_facts):
            raise ValueError("a review outcome needs a review reason or a missing fact")
        if self.outcome is EligibilityOutcome.INSUFFICIENT_DATA and not self.missing_facts:
            raise ValueError("insufficient_data names at least one missing fact")
        if self.outcome is EligibilityOutcome.INDICATIVELY_ELIGIBLE and (
            self.review_reasons or self.missing_facts or not all(result.passed for result in self.rule_results)
        ):
            raise ValueError("indicatively_eligible needs every rule passed, no review reason, and no missing fact")
        if self.outcome is EligibilityOutcome.NOT_ELIGIBLE and not any(
            not result.passed and result.clause_refs for result in self.rule_results
        ):
            raise ValueError("not_eligible names at least one failed rule with a clause reference")
        return self


class UncertaintyStatement(StrEnum):
    INDICATIVE_ONLY = "indicative_only"
    BORDERLINE_ESTIMATE = "borderline_estimate"
    MISSING_INFORMATION = "missing_information"
    ESTIMATE_UNAVAILABLE = "estimate_unavailable"


class ReviewPath(StrEnum):
    SUBMIT_FOR_HUMAN_REVIEW = "submit_for_human_review"
    REQUEST_HUMAN_CONTACT = "request_human_contact"
    PROVIDE_MISSING_INFORMATION = "provide_missing_information"


class EligibilityReason(DomainModel):
    reason_code: Code
    clause: ClauseRef


IndicativeDisclaimer = Literal["indicative_not_an_offer_or_decision"]
INDICATIVE_DISCLAIMER: IndicativeDisclaimer = "indicative_not_an_offer_or_decision"


class EligibilityView(DomainModel):
    """The customer-facing part of an assessment. It never carries the estimate or any profile value."""

    outcome: EligibilityOutcome
    reasons: tuple[EligibilityReason, ...] = ()
    missing_facts: tuple[Code, ...] = ()
    uncertainty: UncertaintyStatement
    review_path: ReviewPath
    disclaimer: IndicativeDisclaimer = INDICATIVE_DISCLAIMER
    synthetic: Literal[True] = True

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.outcome is EligibilityOutcome.INSUFFICIENT_DATA and (
            self.review_path is not ReviewPath.PROVIDE_MISSING_INFORMATION or not self.missing_facts
        ):
            raise ValueError("insufficient_data asks for the missing information")
        return self

    @classmethod
    def from_assessment(cls, assessment: EligibilityAssessment) -> Self:
        reasons = tuple(
            EligibilityReason(reason_code=result.reason_code, clause=result.clause_refs[0])
            for result in assessment.rule_results
            if result.clause_refs
        )
        return cls(
            outcome=assessment.outcome,
            reasons=reasons,
            missing_facts=assessment.missing_facts,
            uncertainty=_uncertainty(assessment),
            review_path=_review_path(assessment.outcome),
        )


def _uncertainty(assessment: EligibilityAssessment) -> UncertaintyStatement:
    if assessment.outcome is EligibilityOutcome.INSUFFICIENT_DATA:
        return UncertaintyStatement.MISSING_INFORMATION
    if ReviewReason.RISK_ESTIMATE_UNAVAILABLE in assessment.review_reasons:
        return UncertaintyStatement.ESTIMATE_UNAVAILABLE
    if ReviewReason.BORDERLINE_RISK_INTERVAL in assessment.review_reasons:
        return UncertaintyStatement.BORDERLINE_ESTIMATE
    return UncertaintyStatement.INDICATIVE_ONLY


def _review_path(outcome: EligibilityOutcome) -> ReviewPath:
    if outcome is EligibilityOutcome.INSUFFICIENT_DATA:
        return ReviewPath.PROVIDE_MISSING_INFORMATION
    if outcome is EligibilityOutcome.INDICATIVELY_ELIGIBLE:
        return ReviewPath.SUBMIT_FOR_HUMAN_REVIEW
    return ReviewPath.REQUEST_HUMAN_CONTACT


# --- Record and handoff entries ------------------------------------------------------------------------------


class RuleVersion(DomainModel):
    rule_id: RuleId
    rule_version: Annotated[int, Field(ge=1)]


class RiskEstimateRecord(DomainModel):
    """A risk estimate as the execution record keeps it (glass box, phase 13). Internal."""

    model: ModelRef
    estimate_id: RiskEstimateId
    probability: Annotated[UnitInterval, Internal()]
    interval_low: Annotated[UnitInterval, Internal()]
    interval_high: Annotated[UnitInterval, Internal()]
    band: Annotated[RiskBand, Internal()]
    flags: tuple[UncertaintyFlag, ...] = ()
    label_definition: Code
    latency_ms: NonNegativeInt

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _check_estimator(self.model)
        _check_interval(self.interval_low, self.probability, self.interval_high)
        _check_flags(self.band, self.flags)
        return self

    @classmethod
    def from_estimate(cls, estimate: RiskEstimate, *, latency_ms: int) -> Self:
        return cls(
            model=estimate.model,
            estimate_id=estimate.estimate_id,
            probability=estimate.probability,
            interval_low=estimate.interval_low,
            interval_high=estimate.interval_high,
            band=estimate.band,
            flags=estimate.flags,
            label_definition=estimate.label_definition,
            latency_ms=latency_ms,
        )


class EligibilityAssessmentRecord(DomainModel):
    """An eligibility assessment as the execution record keeps it: rule ids and versions, not parameters."""

    assessment_id: AssessmentId
    service: ServiceRef
    product_code: CreditProductCode
    outcome: EligibilityOutcome
    rules: tuple[RuleVersion, ...] = ()
    review_reasons: tuple[ReviewReason, ...] = ()
    missing_facts: tuple[Code, ...] = ()
    policy_pack_version: Annotated[str, StringConstraints(min_length=1, max_length=128)]

    @classmethod
    def from_assessment(cls, assessment: EligibilityAssessment) -> Self:
        return cls(
            assessment_id=assessment.assessment_id,
            service=assessment.service,
            product_code=assessment.product_code,
            outcome=assessment.outcome,
            rules=tuple(RuleVersion(rule_id=r.rule_id, rule_version=r.rule_version) for r in assessment.rule_results),
            review_reasons=assessment.review_reasons,
            missing_facts=assessment.missing_facts,
            policy_pack_version=assessment.policy_pack_version,
        )


class CreditReviewRisk(DomainModel):
    """The estimate a human reviewer sees in a handoff. Agents see it; customers never do."""

    band: Annotated[RiskBand, Internal()]
    interval_low: Annotated[UnitInterval, Internal()]
    interval_high: Annotated[UnitInterval, Internal()]
    model: ModelRef
    label_definition: Code

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _check_estimator(self.model)
        if self.interval_low > self.interval_high:
            raise ValueError("the interval must satisfy low <= high")
        return self


class CreditReview(DomainModel):
    """The credit part of a handoff: what was assessed, why a human is needed, and the internal estimate."""

    product_code: CreditProductCode
    application_ref: ApplicationId | None = None
    eligibility_outcome: EligibilityOutcome | None = None
    rule_ids: tuple[RuleId, ...] = ()
    reason_codes: tuple[Code, ...] = ()
    review_reasons: tuple[ReviewReason, ...] = ()
    missing_facts: tuple[Code, ...] = ()
    risk: Annotated[CreditReviewRisk | None, Internal()] = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.eligibility_outcome in REVIEW_OUTCOMES and not (self.review_reasons or self.missing_facts):
            raise ValueError("a review outcome needs a review reason or a missing fact")
        return self

    @classmethod
    def from_assessment(
        cls,
        assessment: EligibilityAssessment,
        *,
        estimate: RiskEstimate | None = None,
        application_ref: ApplicationId | None = None,
        extra_reasons: tuple[ReviewReason, ...] = (),
    ) -> Self:
        """Summarize an assessment for a reviewer; ``extra_reasons`` adds, for example, a contested result."""
        risk = (
            CreditReviewRisk(
                band=estimate.band,
                interval_low=estimate.interval_low,
                interval_high=estimate.interval_high,
                model=estimate.model,
                label_definition=estimate.label_definition,
            )
            if estimate is not None
            else None
        )
        reasons = tuple(dict.fromkeys((*assessment.review_reasons, *extra_reasons)))
        return cls(
            product_code=assessment.product_code,
            application_ref=application_ref,
            eligibility_outcome=assessment.outcome,
            rule_ids=tuple(result.rule_id for result in assessment.rule_results),
            reason_codes=tuple(result.reason_code for result in assessment.rule_results if not result.passed),
            review_reasons=reasons,
            missing_facts=assessment.missing_facts,
            risk=risk,
        )
