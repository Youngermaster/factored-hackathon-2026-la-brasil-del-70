"""Scripted risk estimator and eligibility policy, for tests and the credit port contract suites.

``FakeEligibilityPolicy`` is a scripted stand-in for the synthetic eligibility service (phase 06). It implements
the guard behavior the ``EligibilityPolicy`` port documents (missing data and missing estimates lead to review,
never to an indicative yes), so it passes the same contract suite the real service must pass.
"""

import hashlib
from collections.abc import Mapping
from decimal import Decimal

from bank_agent.domain.base import DomainModel
from bank_agent.domain.decision import ClauseRef, DecisionKind, RuleResult
from bank_agent.domain.eligibility import (
    CreditRiskFeatures,
    EligibilityAssessment,
    EligibilityOutcome,
    ReviewReason,
    RiskBand,
    RiskEstimate,
    ServiceRef,
    UncertaintyFlag,
)
from bank_agent.domain.errors import RiskEstimatorUnavailableError
from bank_agent.domain.identifiers import AssessmentId, IdKind, RiskEstimateId
from bank_agent.domain.intelligence import ModelComponent, ModelRef
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.eligibility import EligibilityRequest

FAKE_RISK_ESTIMATOR = ModelRef(component=ModelComponent.RISK_ESTIMATOR, name="fake", version="1")
FAKE_LABEL_DEFINITION = "fake_adverse_outcome"


class ScriptedRisk(DomainModel):
    """The numbers a scripted estimate returns."""

    probability: Decimal
    interval_low: Decimal
    interval_high: Decimal
    band: RiskBand
    flags: tuple[UncertaintyFlag, ...] = ()


DEFAULT_RISK = ScriptedRisk(
    probability=Decimal("0.10"), interval_low=Decimal("0.06"), interval_high=Decimal("0.15"), band=RiskBand.LOW
)


def feature_digest(features: CreditRiskFeatures) -> str:
    """SHA-256 over the canonical JSON of the features: the key scripts are stored under."""
    return hashlib.sha256(features.model_dump_json().encode("utf-8")).hexdigest()


class FakeRiskEstimator:
    """Implements the ``RiskEstimator`` port from scripts keyed by ``feature_digest``, with a default.

    With ``unavailable=True`` every call raises ``RiskEstimatorUnavailableError``. Calls are recorded.
    """

    def __init__(
        self,
        clock: Clock,
        ids: IdGenerator,
        *,
        default: ScriptedRisk = DEFAULT_RISK,
        scripts: Mapping[str, ScriptedRisk] | None = None,
        unavailable: bool = False,
    ) -> None:
        self._clock = clock
        self._ids = ids
        self._default = default
        self._scripts = dict(scripts or {})
        self.unavailable = unavailable
        self.calls: list[CreditRiskFeatures] = []

    def set(self, features: CreditRiskFeatures, risk: ScriptedRisk) -> None:
        self._scripts[feature_digest(features)] = risk

    def estimate(self, features: CreditRiskFeatures) -> RiskEstimate:
        self.calls.append(features)
        if self.unavailable:
            raise RiskEstimatorUnavailableError("the fake risk estimator is scripted as unavailable")
        risk = self._scripts.get(feature_digest(features), self._default)
        return RiskEstimate(
            estimate_id=RiskEstimateId(self._ids.new(IdKind.RISK_ESTIMATE)),
            model=FAKE_RISK_ESTIMATOR,
            probability=risk.probability,
            interval_low=risk.interval_low,
            interval_high=risk.interval_high,
            band=risk.band,
            flags=risk.flags,
            label_definition=FAKE_LABEL_DEFINITION,
            calibrated=False,
            computed_at=self._clock.now(),
        )


_SCRIPTABLE = frozenset(
    {EligibilityOutcome.INDICATIVELY_ELIGIBLE, EligibilityOutcome.NOT_ELIGIBLE, EligibilityOutcome.REVIEW_REQUIRED}
)
_FACT_REASONS = {
    "credit_score": ReviewReason.MISSING_CREDIT_SCORE,
    "estimated_monthly_income": ReviewReason.MISSING_INCOME,
}


class FakeEligibilityPolicy:
    """Implements the ``EligibilityPolicy`` port: the port's guards first, then a scripted outcome per product.

    Guards, in order: a product without self-service eligibility gives ``review_required``; a missing profile,
    credit score, or income gives ``insufficient_data``; a missing estimate or an ``unknown`` band gives
    ``review_required``. Otherwise the outcome scripted for the product code (default
    ``indicatively_eligible``) is returned. Calls are recorded.
    """

    def __init__(
        self,
        clock: Clock,
        ids: IdGenerator,
        *,
        pack_version: str = "pack-fake-1",
        outcomes: Mapping[str, EligibilityOutcome] | None = None,
    ) -> None:
        outcomes = dict(outcomes or {})
        if not set(outcomes.values()) <= _SCRIPTABLE:
            raise ValueError("insufficient_data comes only from missing facts, never from a script")
        self._clock = clock
        self._ids = ids
        self._pack_version = pack_version
        self._outcomes = outcomes
        self.calls: list[EligibilityRequest] = []

    def _clause(self, request: EligibilityRequest) -> tuple[ClauseRef, ...]:
        ids = request.product.eligibility_clause_ids
        return (ClauseRef(clause_id=ids[0], version=1),) if ids else ()

    def _rule(
        self, request: EligibilityRequest, reason_code: str, *, passed: bool, missing: tuple[str, ...] = ()
    ) -> RuleResult:
        effect = (
            None if passed else (DecisionKind.DENY if reason_code == "fake_not_eligible" else DecisionKind.ESCALATE)
        )
        return RuleResult(
            rule_id="ELG.fake_policy",
            rule_version=1,
            passed=passed,
            effect=effect,
            reason_code=reason_code,
            clause_refs=self._clause(request),
            missing_facts=missing,
        )

    def _assessment(
        self,
        request: EligibilityRequest,
        outcome: EligibilityOutcome,
        rule: RuleResult,
        reasons: tuple[ReviewReason, ...] = (),
        missing: tuple[str, ...] = (),
    ) -> EligibilityAssessment:
        estimate = request.risk_estimate
        return EligibilityAssessment(
            assessment_id=AssessmentId(self._ids.new(IdKind.ASSESSMENT)),
            product_code=request.product.product_code,
            outcome=outcome,
            rule_results=(rule,),
            review_reasons=reasons,
            missing_facts=missing,
            risk_estimate_ref=estimate.ref if estimate is not None else None,
            policy_pack_version=self._pack_version,
            service=ServiceRef(name="synthetic", version=self._pack_version),
            evaluated_at=self._clock.now(),
        )

    def assess(self, request: EligibilityRequest) -> EligibilityAssessment:
        self.calls.append(request)
        review = EligibilityOutcome.REVIEW_REQUIRED
        if not request.product.self_service_eligibility:
            rule = self._rule(request, "fake_human_assessment_required", passed=False)
            return self._assessment(request, review, rule, (ReviewReason.PRODUCT_REQUIRES_HUMAN_ASSESSMENT,))
        profile = request.profile
        missing = (
            ("credit_profile",) if profile is None else tuple(f for f in _FACT_REASONS if getattr(profile, f) is None)
        )
        if missing:
            reasons = tuple(_FACT_REASONS[fact] for fact in missing if fact in _FACT_REASONS)
            rule = self._rule(request, "fake_missing_facts", passed=False, missing=missing)
            return self._assessment(request, EligibilityOutcome.INSUFFICIENT_DATA, rule, reasons, missing)
        estimate = request.risk_estimate
        if estimate is None or estimate.band is RiskBand.UNKNOWN:
            rule = self._rule(request, "fake_estimate_unavailable", passed=False)
            return self._assessment(request, review, rule, (ReviewReason.RISK_ESTIMATE_UNAVAILABLE,))
        outcome = self._outcomes.get(request.product.product_code, EligibilityOutcome.INDICATIVELY_ELIGIBLE)
        if outcome is EligibilityOutcome.NOT_ELIGIBLE:
            return self._assessment(request, outcome, self._rule(request, "fake_not_eligible", passed=False))
        if outcome is EligibilityOutcome.REVIEW_REQUIRED:
            rule = self._rule(request, "fake_borderline", passed=False)
            return self._assessment(request, outcome, rule, (ReviewReason.BORDERLINE_RISK_INTERVAL,))
        return self._assessment(request, outcome, self._rule(request, "fake_indicatively_eligible", passed=True))
