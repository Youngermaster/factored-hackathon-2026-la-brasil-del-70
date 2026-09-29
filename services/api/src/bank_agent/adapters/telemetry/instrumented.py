"""Tracing decorators for the engine's deterministic components, stacked in the composition root.

Each wraps a port and opens one span per call, so a trace shows every router dispatch, policy evaluation, risk
estimate, and eligibility assessment between the turn span and the tool spans. Attributes are ids and codes only:
the intent and its confidence, rule ids and the decision kind, the estimator's model reference (never the
probability, interval, or band), and the eligibility outcome. The wrapped components stay unaware of tracing.
"""

from datetime import date
from typing import Protocol

from bank_agent.domain.base import UntrustedText
from bank_agent.domain.decision import Decision
from bank_agent.domain.eligibility import CreditRiskFeatures, EligibilityAssessment, RiskEstimate
from bank_agent.domain.errors import DomainError
from bank_agent.domain.intelligence import IntentPrediction
from bank_agent.domain.locale import Language
from bank_agent.policy.facts import EvaluationRequest
from bank_agent.policy.pack import PolicyPack
from bank_agent.ports.eligibility import EligibilityPolicy, EligibilityRequest
from bank_agent.ports.models import IntentRouter, RiskEstimator
from bank_agent.ports.telemetry import AttributeValue, Telemetry


class TracedIntentRouter:
    """Implements ``IntentRouter``: a ``bank.router.dispatch`` span per routing call."""

    def __init__(self, inner: IntentRouter, telemetry: Telemetry) -> None:
        self._inner = inner
        self._telemetry = telemetry

    def route(self, text: UntrustedText, language: Language) -> IntentPrediction:
        with self._telemetry.span("bank.router.dispatch", {"bank.language": language.value}) as span:
            prediction = self._inner.route(text, language)
            span.set_attribute("bank.intent", prediction.intent.value)
            span.set_attribute("bank.intent.confidence", float(prediction.confidence))
            span.set_attribute("bank.intent.below_threshold", prediction.below_threshold)
            span.set_attribute("bank.model", str(prediction.model))
            return prediction


class PolicyServicesLike(Protocol):
    """What the engine needs from the policy services (``bootstrap.policy.PolicyServices`` satisfies it)."""

    @property
    def pack(self) -> PolicyPack: ...

    @property
    def data_as_of(self) -> date: ...

    def evaluate(self, request: EvaluationRequest) -> Decision: ...


class TracedPolicyEvaluator:
    """Implements the engine's ``PolicyEvaluator``: a ``bank.policy.evaluate`` span per kernel call."""

    def __init__(self, inner: PolicyServicesLike, telemetry: Telemetry) -> None:
        self._inner = inner
        self._telemetry = telemetry

    @property
    def pack(self) -> PolicyPack:
        return self._inner.pack

    @property
    def data_as_of(self) -> date:
        return self._inner.data_as_of

    def evaluate(self, request: EvaluationRequest) -> Decision:
        attributes: dict[str, AttributeValue] = {
            "bank.workflow": request.workflow.value,
            "bank.policy.state": request.state,
        }
        with self._telemetry.span("bank.policy.evaluate", attributes) as span:
            decision = self._inner.evaluate(request)
            span.set_attribute("bank.policy.decision", decision.kind.value)
            span.set_attribute("bank.policy.decisive_rules", ",".join(decision.decisive_rule_ids)[:512])
            span.set_attribute("bank.policy.pack_version", self._inner.pack.version)
            return decision


class TracedRiskEstimator:
    """Implements ``RiskEstimator``: a ``bank.risk.estimate`` span naming the model, never the estimate."""

    def __init__(self, inner: RiskEstimator, telemetry: Telemetry) -> None:
        self._inner = inner
        self._telemetry = telemetry

    def estimate(self, features: CreditRiskFeatures) -> RiskEstimate:
        with self._telemetry.span(
            "bank.risk.estimate", {"bank.credit.product_type": features.product_type.value}
        ) as span:
            try:
                estimate = self._inner.estimate(features)
            except DomainError as error:
                span.record_error_code(error.code)
                raise
            span.set_attribute("bank.model", str(estimate.model))
            return estimate


class TracedEligibilityPolicy:
    """Implements ``EligibilityPolicy``: a ``bank.eligibility.assess`` span with the outcome and the rule ids."""

    def __init__(self, inner: EligibilityPolicy, telemetry: Telemetry) -> None:
        self._inner = inner
        self._telemetry = telemetry

    def assess(self, request: EligibilityRequest) -> EligibilityAssessment:
        attributes: dict[str, AttributeValue] = {
            "bank.credit.product": str(request.product.product_code),
            "bank.risk_estimate.present": request.risk_estimate is not None,
        }
        with self._telemetry.span("bank.eligibility.assess", attributes) as span:
            try:
                assessment = self._inner.assess(request)
            except DomainError as error:
                span.record_error_code(error.code)
                raise
            span.set_attribute("bank.eligibility.outcome", assessment.outcome.value)
            span.set_attribute("bank.eligibility.review_reasons", ",".join(r.value for r in assessment.review_reasons))
            return assessment
