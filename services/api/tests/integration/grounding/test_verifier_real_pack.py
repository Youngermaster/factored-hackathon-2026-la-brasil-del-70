"""The verifier over the pack's own texts: every bound explanation and every eligibility answer is grounded."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bank_agent.adapters.policy.filesystem import FilesystemCreditCatalog, FilesystemPolicyRepository
from bank_agent.application.grounding.bound import BoundPolicyLookup
from bank_agent.application.grounding.draft import GroundingContext, ResponseDraft, ViolationKind
from bank_agent.application.grounding.verifier import GroundingVerifier
from bank_agent.bootstrap.settings import DEFAULT_DATA_AS_OF, DEFAULT_POLICY_DIR
from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.eligibility import EligibilityAssessment, EligibilityOutcome, EligibilityView, RiskEstimate
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.locale import Country, Language, Locale
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_agent.policy.eligibility import SyntheticEligibilityService, render_eligibility
from bank_agent.policy.explain import explain
from bank_agent.ports.eligibility import CreditApplicationFacts, EligibilityRequest
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import CUSTOMER_A, T0, customer, risk_estimate

REPOSITORY = FilesystemPolicyRepository.from_directory(DEFAULT_POLICY_DIR)
PACK = REPOSITORY.pack
CATALOG = FilesystemCreditCatalog.from_directory(DEFAULT_POLICY_DIR, PACK)
LOOKUP = BoundPolicyLookup(REPOSITORY)
VERIFIER = GroundingVerifier(REPOSITORY)
LOCALES = {Language.ES: None, Language.PT: Locale.PT_BR, Language.EN: Locale.EN_US}
CASES = [
    (descriptor.id, state, country, language)
    for descriptor in WORKFLOW_CATALOG.descriptors
    for state in descriptor.states
    for country in Country
    for language in Language
]


def locale(country: Country, language: Language) -> Locale:
    return LOCALES[language] or country.default_locale


@pytest.mark.parametrize(("workflow", "state", "country", "language"), CASES)
def test_every_bound_explanation_passes_the_verifier(
    workflow: WorkflowId, state: str, country: Country, language: Language
) -> None:
    bound = LOOKUP.for_state(workflow, state, customer(country=country), language)
    rendered = explain(PACK, bound.refs, language, locale(country, language))
    context = GroundingContext(
        workflow=workflow, language=language, jurisdiction=country, currency=country.default_currency
    )
    assert VERIFIER.verify(ResponseDraft(text=rendered.text, citations=rendered.citations), context) == ()


def assess(score: int | None, income: str | None, estimate: RiskEstimate | None) -> EligibilityAssessment:
    product = CATALOG.get(CreditProductCode("CO-PL-STANDARD"))
    assert product is not None
    profile = CreditProfile(
        customer_id=CUSTOMER_A,
        credit_score=score,
        estimated_monthly_income=Money.of(income, Currency.COP) if income else None,
        tenure_months=60,
        max_days_past_due=0,
        as_of=DEFAULT_DATA_AS_OF,
    )
    request = EligibilityRequest(
        product=product,
        profile=profile,
        application=CreditApplicationFacts(
            requested_amount=Money.of("20000000.00", Currency.COP), requested_term_months=36, purpose="general_purpose"
        ),
        risk_estimate=estimate,
        jurisdiction=Country.CO,
        as_of=datetime(2026, 9, 27, tzinfo=UTC),
    )
    return SyntheticEligibilityService(PACK, FixedClock(T0), SequentialIdGenerator()).assess(request)


LOW = risk_estimate(interval_low=Decimal("0.05"), probability=Decimal("0.08"), interval_high=Decimal("0.12"))
ASSESSMENTS = {
    EligibilityOutcome.INDICATIVELY_ELIGIBLE: assess(760, "30000000.00", LOW),
    EligibilityOutcome.NOT_ELIGIBLE: assess(520, "30000000.00", LOW),
    EligibilityOutcome.REVIEW_REQUIRED: assess(760, "30000000.00", None),
    EligibilityOutcome.INSUFFICIENT_DATA: assess(760, None, LOW),
}


@pytest.mark.parametrize("outcome", list(EligibilityOutcome))
@pytest.mark.parametrize("language", list(Language))
def test_every_eligibility_answer_is_grounded_in_its_own_assessment(
    outcome: EligibilityOutcome, language: Language
) -> None:
    assessment = ASSESSMENTS[outcome]
    assert assessment.outcome is outcome
    rendered = render_eligibility(
        PACK, EligibilityView.from_assessment(assessment), language, locale(Country.CO, language)
    )
    draft = ResponseDraft(text=rendered.text, citations=rendered.citations)
    context = GroundingContext(
        workflow=WorkflowId.CREDIT,
        language=language,
        jurisdiction=Country.CO,
        currency=Currency.COP,
        eligibility=assessment,
        catalog_product=CATALOG.get(CreditProductCode("CO-PL-STANDARD")),
        risk_estimate=LOW,
    )
    assert VERIFIER.verify(draft, context) == ()
    other = next(a for o, a in ASSESSMENTS.items() if o is not outcome)
    mismatched = VERIFIER.verify(draft, context.model_copy(update={"eligibility": other}))
    assert {v.kind for v in mismatched} == {ViolationKind.ELIGIBILITY_OUTCOME_MISMATCH}
