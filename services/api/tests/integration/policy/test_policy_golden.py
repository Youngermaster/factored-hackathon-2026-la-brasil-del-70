"""Golden texts of the explanation renderer, in Spanish and Portuguese, from the real pack.

A golden file changes only with a reviewed clause or message change; regenerate with
``UPDATE_POLICY_GOLDEN=1 uv run pytest services/api/tests/integration/policy/test_policy_golden.py`` and review
the diff like any clause edit.
"""

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from bank_agent.adapters.policy.filesystem import FilesystemCreditCatalog, FilesystemPolicyRepository
from bank_agent.bootstrap.settings import DEFAULT_DATA_AS_OF, DEFAULT_POLICY_DIR
from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.eligibility import EligibilityView
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.locale import Country, Language, Locale
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.policy.eligibility import SyntheticEligibilityService, render_eligibility
from bank_agent.policy.evaluator import evaluate
from bank_agent.policy.explain import RenderedExplanation, explain_decision
from bank_agent.policy.facts import DisputeFacts, EvaluationRequest, PolicyFacts
from bank_agent.ports.eligibility import CreditApplicationFacts, EligibilityRequest
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import CUSTOMER_A, T0, risk_estimate
from bank_agent_policy import snapshot, transaction_facts

GOLDEN = Path(__file__).parent / "golden"
PACK = FilesystemPolicyRepository.from_directory(DEFAULT_POLICY_DIR).pack
CATALOG = FilesystemCreditCatalog.from_directory(DEFAULT_POLICY_DIR, PACK)
LOCALES = {(Country.CO, Language.ES): Locale.ES_CO, (Country.CO, Language.PT): Locale.PT_BR}


def _check(name: str, rendered: RenderedExplanation) -> None:
    path = GOLDEN / f"{name}.{rendered.language.value}.txt"
    text = rendered.text + "\n\n" + " ".join(str(ref) for ref in rendered.citations) + "\n"
    if os.environ.get("UPDATE_POLICY_GOLDEN") == "1":
        path.write_text(text, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == text


@pytest.mark.parametrize("language", [Language.ES, Language.PT])
def test_a_closed_dispute_window_is_explained_from_the_clause(language: Language) -> None:
    amount = Money.of("150000.00", Currency.COP)
    facts = PolicyFacts(
        jurisdiction=Country.CO,
        data_as_of=DEFAULT_DATA_AS_OF,
        intent=Intent.DISPUTE_NEW,
        dispute=DisputeFacts(
            transaction=transaction_facts(occurred_on=date(2026, 3, 1), amount=amount),
            reason=DisputeReason.UNRECOGNIZED,
            disputed_amount=amount,
        ),
    )
    request = EvaluationRequest(workflow=WorkflowId.DISPUTE, state="COLLECT_DETAILS", session=snapshot(), facts=facts)
    rendered = explain_decision(PACK, evaluate(request, PACK), language, LOCALES[(Country.CO, language)])
    _check("dispute-window-closed-co", rendered)


@pytest.mark.parametrize("language", [Language.ES, Language.PT])
def test_an_amount_above_the_automatic_limit_is_explained_with_the_local_currency(language: Language) -> None:
    amount = Money.of("2500000.00", Currency.COP)
    facts = PolicyFacts(
        jurisdiction=Country.CO,
        data_as_of=DEFAULT_DATA_AS_OF,
        intent=Intent.DISPUTE_NEW,
        dispute=DisputeFacts(
            transaction=transaction_facts(occurred_on=date(2026, 6, 1), amount=amount),
            reason=DisputeReason.UNRECOGNIZED,
            disputed_amount=amount,
        ),
    )
    request = EvaluationRequest(workflow=WorkflowId.DISPUTE, state="CONFIRM_DISPUTE", session=snapshot(), facts=facts)
    rendered = explain_decision(PACK, evaluate(request, PACK), language, LOCALES[(Country.CO, language)])
    _check("dispute-amount-above-limit-co", rendered)


@pytest.mark.parametrize("language", [Language.ES, Language.PT])
def test_an_insufficient_data_eligibility_answer(language: Language) -> None:
    product = CATALOG.get(CreditProductCode("CO-PL-STANDARD"))
    assert product is not None
    request = EligibilityRequest(
        product=product,
        profile=CreditProfile(
            customer_id=CUSTOMER_A, credit_score=700, tenure_months=60, max_days_past_due=0, as_of=DEFAULT_DATA_AS_OF
        ),
        application=CreditApplicationFacts(
            requested_amount=Money.of("20000000.00", Currency.COP), requested_term_months=36, purpose="general_purpose"
        ),
        risk_estimate=risk_estimate(
            interval_low=Decimal("0.05"), probability=Decimal("0.08"), interval_high=Decimal("0.12")
        ),
        jurisdiction=Country.CO,
        as_of=datetime(2026, 9, 27, tzinfo=UTC),
    )
    assessment = SyntheticEligibilityService(PACK, FixedClock(T0), SequentialIdGenerator()).assess(request)
    view = EligibilityView.from_assessment(assessment)
    rendered = render_eligibility(PACK, view, language, LOCALES[(Country.CO, language)])
    _check("eligibility-insufficient-data-co", rendered)
