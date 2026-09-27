"""The synthetic eligibility service: the ``EligibilityPolicy`` port over the ELG rules of the policy pack.

It is synthetic and says so in every output. It never approves anything, never calls a model, and never
computes a risk estimate: the estimate is an input fact. Outcome mapping, first match wins:

1. A product without self-service eligibility (a mortgage): ``review_required`` with
   ``product_requires_human_assessment``; no other rule runs.
2. Any rule with a missing fact: ``insufficient_data``, naming the facts.
3. Any rule asking for review (estimate unavailable or ``unknown``, borderline interval, days past due above
   the maximum, amount above the review threshold): ``review_required`` with its review reasons.
4. Any other failed rule: ``not_eligible``.
5. Every rule passed: ``indicatively_eligible``.
"""

from bank_agent.domain.decision import DecisionKind, RuleResult
from bank_agent.domain.eligibility import EligibilityAssessment, EligibilityOutcome, ReviewReason, ServiceRef
from bank_agent.domain.errors import EligibilityServiceUnavailableError
from bank_agent.domain.identifiers import AssessmentId, IdKind
from bank_agent.domain.locale import Language
from bank_agent.domain.policy import Jurisdiction, PolicyClause
from bank_agent.policy.pack import PolicyPack
from bank_agent.policy.rules import ELIGIBILITY_RULES, EligibilityContext
from bank_agent.policy.selection import ParamConflictError, eligibility_clauses, merge_params, refs
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.eligibility import EligibilityRequest

SERVICE_NAME = "synthetic"
SELF_SERVICE_RULE = "ELG.self_service_product"
REVIEW_REASON_BY_CODE = {
    "product_requires_human_assessment": ReviewReason.PRODUCT_REQUIRES_HUMAN_ASSESSMENT,
    "risk_estimate_unavailable": ReviewReason.RISK_ESTIMATE_UNAVAILABLE,
    "borderline_risk_interval": ReviewReason.BORDERLINE_RISK_INTERVAL,
    "days_past_due_present": ReviewReason.DAYS_PAST_DUE_PRESENT,
    "amount_above_review_threshold": ReviewReason.AMOUNT_ABOVE_REVIEW_THRESHOLD,
}
REVIEW_REASON_BY_FACT = {
    "credit_score": ReviewReason.MISSING_CREDIT_SCORE,
    "monthly_income": ReviewReason.MISSING_INCOME,
}


def map_outcome(
    results: tuple[RuleResult, ...],
) -> tuple[EligibilityOutcome, tuple[ReviewReason, ...], tuple[str, ...]]:
    """The outcome, review reasons, and missing facts for ordered rule results (steps 2 to 5 above)."""
    missing = tuple(dict.fromkeys(fact for result in results for fact in result.missing_facts))
    if missing:
        reasons = tuple(REVIEW_REASON_BY_FACT[fact] for fact in missing if fact in REVIEW_REASON_BY_FACT)
        return EligibilityOutcome.INSUFFICIENT_DATA, reasons, missing
    review = [r for r in results if not r.passed and r.effect is DecisionKind.ESCALATE]
    if review:
        reasons = tuple(dict.fromkeys(REVIEW_REASON_BY_CODE[r.reason_code] for r in review))
        return EligibilityOutcome.REVIEW_REQUIRED, reasons, ()
    if any(not result.passed for result in results):
        return EligibilityOutcome.NOT_ELIGIBLE, (), ()
    return EligibilityOutcome.INDICATIVELY_ELIGIBLE, (), ()


class SyntheticEligibilityService:
    """Implements ``EligibilityPolicy``. Deterministic for the same request and pack; ids and time are injected."""

    def __init__(self, pack: PolicyPack, clock: Clock, ids: IdGenerator) -> None:
        self._pack = pack
        self._clock = clock
        self._ids = ids
        self.service = ServiceRef(name=SERVICE_NAME, version=pack.version)

    def _clauses(self, request: EligibilityRequest) -> tuple[PolicyClause, ...]:
        product = request.product
        current = self._pack.list_clauses(language=Language.ES, jurisdiction=request.jurisdiction)
        clauses = eligibility_clauses(current, request.jurisdiction, product.product_type.value)
        specific = [c for c in clauses if c.metadata.jurisdiction is not Jurisdiction.ALL]
        if product.self_service_eligibility and len(specific) != 1:
            raise EligibilityServiceUnavailableError("the policy pack has no ELG parameters for this product type")
        return clauses

    def _run(self, rule_id: str, request: EligibilityRequest, clauses: tuple[PolicyClause, ...]) -> RuleResult:
        try:
            params = merge_params(clauses)
        except ParamConflictError as error:
            raise EligibilityServiceUnavailableError(str(error)) from error
        binding = tuple(clause for clause in clauses if rule_id in clause.metadata.bound_rules)
        return ELIGIBILITY_RULES[rule_id].run(EligibilityContext(request=request, params=params), refs(binding))

    def rule_results(self, request: EligibilityRequest) -> tuple[RuleResult, ...]:
        clauses = self._clauses(request)
        first = self._run(SELF_SERVICE_RULE, request, clauses)
        if not first.passed:
            return (first,)
        others = (rule_id for rule_id in ELIGIBILITY_RULES.order() if rule_id != SELF_SERVICE_RULE)
        rest = (self._run(rule_id, request, clauses) for rule_id in others)
        return (first, *rest)

    def assess(self, request: EligibilityRequest) -> EligibilityAssessment:
        results = self.rule_results(request)
        outcome, reasons, missing = map_outcome(results)
        estimate = request.risk_estimate
        return EligibilityAssessment(
            assessment_id=AssessmentId(self._ids.new(IdKind.ASSESSMENT)),
            product_code=request.product.product_code,
            outcome=outcome,
            rule_results=results,
            review_reasons=reasons,
            missing_facts=missing,
            risk_estimate_ref=estimate.ref if estimate is not None else None,
            policy_pack_version=self._pack.version,
            service=self.service,
            evaluated_at=self._clock.now(),
        )
