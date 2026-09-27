"""Credit flow data and intake keys: a card has no term, and an intake key follows the assessment it confirms."""

from bank_agent.application.engine.idempotency import derive_key
from bank_agent.application.workflows.credit.data import CARD_TERM_MONTHS, CreditData, open_questions
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.identifiers import SourceRef, SourceTable
from bank_agent.domain.workflow import Intent


def test_a_card_records_the_billing_cycle_and_a_loan_its_term() -> None:
    data = CreditData(term_months=24)
    assert data.term_for(CreditProductType.CREDIT_CARD) == CARD_TERM_MONTHS == 1
    assert data.term_for(CreditProductType.PERSONAL_LOAN) == 24
    assert CreditData().term_for(CreditProductType.PERSONAL_LOAN) is None


def test_open_questions_name_the_missing_application_facts() -> None:
    data = CreditData(intent=Intent.CREDIT_ELIGIBILITY, product_type=CreditProductType.PERSONAL_LOAN)
    assert open_questions(data) == ("What amount does the customer ask for?", "What term does the customer want?")
    assert open_questions(CreditData(intent=Intent.CREDIT_PRODUCT_INFO)) == ()


def test_intake_keys_are_stable_per_assessment_and_differ_across_assessments() -> None:
    target = SourceRef.of(SourceTable.CREDIT_PRODUCTS, "MX-CC-CLASSIC")
    action = ActionKind.SUBMIT_CREDIT_APPLICATION
    first = derive_key("conv-000001|elg-000001", target, action)
    assert first == derive_key("conv-000001|elg-000001", target, action)
    assert first != derive_key("conv-000001|elg-000002", target, action)
    assert first.startswith("wf-")
