"""Tracing decorators for the router, the policy kernel, the risk estimator, and the eligibility service."""

from dataclasses import dataclass
from datetime import date

import pytest

from bank_agent.adapters.telemetry.instrumented import (
    TracedEligibilityPolicy,
    TracedIntentRouter,
    TracedPolicyEvaluator,
    TracedRiskEstimator,
)
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.credit import CreditProductType, CreditProfile
from bank_agent.domain.decision import Decision
from bank_agent.domain.eligibility import CreditRiskFeatures
from bank_agent.domain.errors import RiskEstimatorUnavailableError
from bank_agent.domain.identifiers import CustomerId
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.policy.facts import EvaluationRequest
from bank_agent.ports.eligibility import CreditApplicationFacts, EligibilityRequest
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.credit import FakeEligibilityPolicy, FakeRiskEstimator
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent.testing.models import FakeIntentRouter
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_builders import CUSTOMER_A, T0, decision
from bank_agent_credit import catalog_products

FEATURES = CreditRiskFeatures(
    jurisdiction=Country.MX, product_type=CreditProductType.PERSONAL_LOAN, requested_term_months=24, credit_score=700
)


def test_the_router_span_names_the_intent_confidence_and_model() -> None:
    telemetry = RecordingTelemetry()
    router = TracedIntentRouter(FakeIntentRouter(scripts={"saldo": (Intent.BALANCE_INQUIRY, 0.9)}), telemetry)
    prediction = router.route(UntrustedText("saldo"), Language.ES)
    (span,) = telemetry.spans
    assert span.name == "bank.router.dispatch"
    assert span.attributes == {
        "bank.language": "es",
        "bank.intent": prediction.intent.value,
        "bank.intent.confidence": 0.9,
        "bank.intent.below_threshold": False,
        "bank.model": str(prediction.model),
    }


def test_the_risk_span_names_the_model_and_never_the_estimate() -> None:
    telemetry = RecordingTelemetry()
    clock, ids = FixedClock(T0), SequentialIdGenerator()
    estimate = TracedRiskEstimator(FakeRiskEstimator(clock, ids), telemetry).estimate(FEATURES)
    (span,) = telemetry.spans
    assert span.attributes == {"bank.credit.product_type": "personal_loan", "bank.model": str(estimate.model)}
    assert str(estimate.probability) not in str(span.attributes.values())


def test_a_failed_estimate_marks_the_span_and_propagates() -> None:
    telemetry = RecordingTelemetry()
    unavailable = FakeRiskEstimator(FixedClock(T0), SequentialIdGenerator(), unavailable=True)
    with pytest.raises(RiskEstimatorUnavailableError):
        TracedRiskEstimator(unavailable, telemetry).estimate(FEATURES)
    assert telemetry.spans[0].error_codes == ["risk_estimator_unavailable"]


def test_the_eligibility_span_names_the_product_and_outcome() -> None:
    telemetry = RecordingTelemetry()
    product = catalog_products()[0]
    request = EligibilityRequest(
        product=product,
        profile=CreditProfile(customer_id=CustomerId(CUSTOMER_A), credit_score=700, as_of=date(2026, 6, 1)),
        application=CreditApplicationFacts(
            requested_amount=Money.of("40000", Currency.MXN), requested_term_months=24, purpose="debt_consolidation"
        ),
        jurisdiction=Country.MX,
        as_of=T0,
    )
    service = TracedEligibilityPolicy(FakeEligibilityPolicy(FixedClock(T0), SequentialIdGenerator()), telemetry)
    assessment = service.assess(request)
    (span,) = telemetry.spans
    assert span.name == "bank.eligibility.assess"
    assert span.attributes["bank.eligibility.outcome"] == assessment.outcome.value
    assert span.attributes["bank.risk_estimate.present"] is False


@dataclass
class _Policy:
    pack: object
    data_as_of: date
    result: Decision

    def evaluate(self, request: EvaluationRequest) -> Decision:
        return self.result


@dataclass
class _Request:
    workflow: WorkflowId
    state: str


def test_the_policy_span_names_the_state_decision_and_rules() -> None:
    telemetry = RecordingTelemetry()

    @dataclass
    class _Pack:
        version: str = "pack-fixture-1"

    inner = _Policy(pack=_Pack(), data_as_of=date(2026, 6, 17), result=decision())
    evaluator = TracedPolicyEvaluator(inner, telemetry)  # type: ignore[arg-type]
    assert evaluator.data_as_of == date(2026, 6, 17)
    evaluator.evaluate(_Request(WorkflowId.DISPUTE, "UNDERSTAND"))  # type: ignore[arg-type]
    (span,) = telemetry.spans
    assert span.name == "bank.policy.evaluate"
    assert span.attributes["bank.workflow"] == "dispute"
    assert span.attributes["bank.policy.decision"] == "allow"
    assert span.attributes["bank.policy.pack_version"] == "pack-fixture-1"
