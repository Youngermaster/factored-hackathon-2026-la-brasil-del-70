"""ESTIMATE_RISK and ASSESS_ELIGIBILITY: the two credit components the engine calls itself, kept apart.

- ESTIMATE_RISK reads the credit profile through the engine-only tool (recorded, no values), builds the
  ``CreditRiskFeatures`` allowlist, and calls the ``RiskEstimator`` port. ``RiskEstimatorUnavailableError`` yields no
  estimate, never a default; the eligibility service then asks for human review.
- ASSESS_ELIGIBILITY calls the ``EligibilityPolicy`` port (the synthetic service) with the catalog entry, the
  profile, the customer's application facts, and the estimate or ``None``.

The estimate and the assessment go into the execution record as separate entries. The profile and the estimate live
for this turn only (``turn_values``): they are never persisted, never rendered, and never sent to a model.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from bank_agent.application.engine.context import CreditPorts, Step, TurnContext
from bank_agent.application.engine.shared import escalate
from bank_agent.application.workflows.credit.data import DEFAULT_PURPOSE, CreditData, load, save
from bank_agent.application.workflows.credit.info import product_of
from bank_agent.domain.credit import CreditProduct, CreditProfile
from bank_agent.domain.eligibility import (
    CreditRiskFeatures,
    EligibilityAssessment,
    EligibilityAssessmentRecord,
    RiskEstimate,
    RiskEstimateRecord,
)
from bank_agent.domain.errors import EligibilityServiceUnavailableError, RiskEstimatorUnavailableError
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.identifiers import SourceRef, SourceTable
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Money
from bank_agent.ports.eligibility import CreditApplicationFacts, EligibilityRequest

PROFILE, ESTIMATE = "credit_profile", "risk_estimate"


def application_facts(data: CreditData, product: CreditProduct) -> CreditApplicationFacts | None:
    term = data.term_for(product.product_type)
    if data.amount is None or term is None:
        return None
    income = (
        data.declared_income if data.declared_income and data.declared_income.currency is product.currency else None
    )
    return CreditApplicationFacts(
        requested_amount=Money.of(str(data.amount), product.currency),
        requested_term_months=term,
        purpose=data.purpose or DEFAULT_PURPOSE,
        declared_monthly_income=income,
    )


def build_features(
    country: Country, product: CreditProduct, application: CreditApplicationFacts, profile: CreditProfile | None
) -> CreditRiskFeatures:
    """The estimator's inputs: the allowlist only. Income stays in the product currency for the ratio (no exchange
    rates in the data), so ``monthly_income_usd`` is unset."""
    income = profile.estimated_monthly_income if profile is not None else None
    income = income or application.declared_monthly_income
    ratio = None
    if income is not None and income.amount > 0 and income.currency is application.requested_amount.currency:
        ratio = (application.requested_amount.amount / income.amount).quantize(Decimal("0.0001"), ROUND_HALF_UP)
    return CreditRiskFeatures(
        jurisdiction=country,
        product_type=product.product_type,
        requested_term_months=application.requested_term_months,
        credit_score=profile.credit_score if profile is not None else None,
        tenure_months=profile.tenure_months if profile is not None else None,
        credit_product_count=profile.credit_product_count if profile is not None else None,
        max_days_past_due=profile.max_days_past_due if profile is not None else None,
        utilization=profile.utilization if profile is not None else None,
        requested_amount_to_income=ratio,
    )


@dataclass(frozen=True)
class Estimated:
    estimate: RiskEstimate | None
    record: RiskEstimateRecord | None


def estimate_risk(ports: CreditPorts, features: CreditRiskFeatures) -> Estimated:
    """The estimate, or no estimate when the estimator is unavailable (never a default)."""
    started = time.perf_counter()
    try:
        estimate = ports.risk_estimator.estimate(features)
    except RiskEstimatorUnavailableError:
        return Estimated(None, None)
    latency = max(0, round((time.perf_counter() - started) * 1000))
    return Estimated(estimate, RiskEstimateRecord.from_estimate(estimate, latency_ms=latency))


def assess(
    ports: CreditPorts,
    product: CreditProduct,
    profile: CreditProfile | None,
    application: CreditApplicationFacts,
    estimate: RiskEstimate | None,
    *,
    now: datetime,
) -> EligibilityAssessment:
    request = EligibilityRequest(
        product=product,
        profile=profile,
        application=application,
        risk_estimate=estimate,
        jurisdiction=product.jurisdiction,
        as_of=now,
    )
    return ports.eligibility.assess(request)


async def read_profile(ctx: TurnContext) -> CreditProfile | None:
    if PROFILE not in ctx.turn_values:
        ctx.turn_values[PROFILE] = await ctx.tools.engine_credit_profile(ctx.profile_reader())
    profile = ctx.turn_values[PROFILE]
    return profile if isinstance(profile, CreditProfile) else None


async def estimate_in_turn(ctx: TurnContext, product: CreditProduct, application: CreditApplicationFacts) -> None:
    """Read the profile, estimate, record the estimate, and keep both for this turn only."""
    profile = await read_profile(ctx)
    result = estimate_risk(ctx.services.credit, build_features(ctx.customer.country, product, application, profile))
    if result.estimate is None or result.record is None:
        ctx.recorder.intervention("risk_estimate_unavailable")
    else:
        ctx.recorder.model(result.estimate.model)
        ctx.recorder.risk_estimates.append(result.record)
    ctx.turn_values[ESTIMATE] = result.estimate


def turn_profile(ctx: TurnContext) -> CreditProfile | None:
    value = ctx.turn_values.get(PROFILE)
    return value if isinstance(value, CreditProfile) else None


def turn_estimate(ctx: TurnContext) -> RiskEstimate | None:
    value = ctx.turn_values.get(ESTIMATE)
    return value if isinstance(value, RiskEstimate) else None


async def estimate_step(ctx: TurnContext) -> Step:
    data = load(ctx)
    product = await product_of(ctx, data.product_type) if data.product_type is not None else None
    application = application_facts(data, product) if product is not None else None
    if product is None or application is None:
        return Step("COLLECT_APPLICATION_FACTS")
    await estimate_in_turn(ctx, product, application)
    return Step("ASSESS_ELIGIBILITY")


async def assess_step(ctx: TurnContext) -> Step:
    data = load(ctx)
    product = await product_of(ctx, data.product_type) if data.product_type is not None else None
    application = application_facts(data, product) if product is not None else None
    if product is None or application is None:
        return Step("COLLECT_APPLICATION_FACTS")
    try:
        assessment = assess(ctx.services.credit, product, await read_profile(ctx), application, turn_estimate(ctx),
                            now=ctx.now)  # fmt: skip
    except EligibilityServiceUnavailableError as error:
        return escalate(ctx, EscalationReasonCode.OTHER, error.code)
    ctx.recorder.eligibility_assessments.append(EligibilityAssessmentRecord.from_assessment(assessment))
    evidence = SourceRef.of(SourceTable.ELIGIBILITY_ASSESSMENTS, assessment.assessment_id)
    ctx.engine = ctx.engine.with_fact(
        f"synthetic eligibility assessment for {product.product_code}: {assessment.outcome.value}", evidence
    )
    save(ctx, data.evolve(assessment=assessment, explained=False))
    return Step("EXPLAIN_ELIGIBILITY")
