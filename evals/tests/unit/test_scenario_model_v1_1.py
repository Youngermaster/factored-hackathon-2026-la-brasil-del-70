"""Version 1.1.0 of the scenario contract: workflows, credit fixtures and assertions, new disclosure kinds."""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from bank_agent.domain.credit import ApplicationStatus
from bank_agent.domain.eligibility import EligibilityOutcome
from bank_agent.domain.intelligence import ModelComponent
from bank_agent.domain.workflow import WorkflowId
from bank_evals.scenarios.model import (
    CreditApplicationCount,
    CreditApplicationExists,
    CreditProfileOverride,
    DisclosureKind,
    EligibilityOutcomeIs,
    ExistingCreditApplication,
    ModelUnavailable,
    Scenario,
)

SCHEMA = Path(__file__).resolve().parents[3] / "contracts" / "schemas" / "scenario.v1.json"

CREDIT: dict[str, Any] = {
    "id": "credit-missing-income-pt-001",
    "split": "dev",
    "language": "pt",
    "dialect": "pt-BR",
    "category": "missing_or_incorrect_data",
    "persona_ref": "persona-mx-credit",
    "goal": "Ask whether a personal loan is possible while the income on file is missing.",
    "mode": "scripted",
    "turns": [{"text": "Posso pedir um emprestimo pessoal?"}],
    "workflow": "credit",
    "expected_eligibility_outcome": "insufficient_data",
    "fixtures": [
        {"kind": "credit_profile_override", "fact": "estimated_monthly_income", "value": None},
        {"kind": "credit_profile_override", "fact": "credit_score", "value": 640},
        {"kind": "existing_credit_application", "product_code": "MX-CC-FIXTURE", "status": "under_human_review"},
        {"kind": "model_unavailable", "component": "risk_estimator"},
    ],
    "expected_outcome": "clarified",
    "expected_state_assertions": [
        {"kind": "credit_application_exists", "product_code": "MX-CC-FIXTURE"},
        {"kind": "credit_application_count", "count": 1},
        {"kind": "eligibility_outcome", "outcome": "insufficient_data"},
    ],
    "required_disclosures": [{"kind": "review_path"}, {"kind": "eligibility_reason"}],
    "forbidden_disclosures": [
        {"kind": "credit_approval_claim"},
        {"kind": "risk_estimate"},
        {"kind": "credit_score"},
        {"kind": "income"},
    ],
    "in_scope": True,
    "provenance": "team_generated",
}


def credit(**overrides: Any) -> Scenario:
    return Scenario.model_validate({**CREDIT, **overrides})


def test_parses_a_credit_scenario_with_every_new_kind() -> None:
    scenario = credit()
    assert scenario.schema_version == "1.4.0"
    assert scenario.workflow is WorkflowId.CREDIT
    assert scenario.expected_eligibility_outcome is EligibilityOutcome.INSUFFICIENT_DATA
    kinds = [type(item) for item in scenario.fixtures]
    assert kinds == [CreditProfileOverride, CreditProfileOverride, ExistingCreditApplication, ModelUnavailable]
    assert [type(item) for item in scenario.expected_state_assertions] == [
        CreditApplicationExists,
        CreditApplicationCount,
        EligibilityOutcomeIs,
    ]
    fixture = scenario.fixtures[2]
    assert isinstance(fixture, ExistingCreditApplication)
    assert fixture.status is ApplicationStatus.UNDER_HUMAN_REVIEW
    unavailable = scenario.fixtures[3]
    assert isinstance(unavailable, ModelUnavailable)
    assert unavailable.component is ModelComponent.RISK_ESTIMATOR


def test_fits_the_committed_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(CREDIT)) == []
    assert schema["properties"]["workflow"]["x-added-in"] == "1.1.0"


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ({"fact": "credit_score", "value": 900}, "between 300 and 850"),
        ({"fact": "credit_score", "value": {"amount": "1", "currency": "MXN"}}, "integer"),
        ({"fact": "estimated_monthly_income", "value": 5000}, "money"),
        ({"fact": "estimated_monthly_income", "value": {"amount": "-1", "currency": "MXN"}}, "non-negative"),
        ({"fact": "max_days_past_due", "value": -3}, "negative"),
        ({"fact": "segment", "value": 1}, "fact"),
    ],
)
def test_credit_profile_overrides_are_validated_per_fact(fixture: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        CreditProfileOverride.model_validate(fixture)


def test_a_days_past_due_override_and_a_money_income_are_accepted() -> None:
    assert CreditProfileOverride(fact="max_days_past_due", value=30).value == 30
    income = CreditProfileOverride.model_validate(
        {"fact": "estimated_monthly_income", "value": {"amount": "25000.00", "currency": "MXN"}}
    )
    assert income.value is not None


def test_an_out_of_scope_scenario_has_no_workflow() -> None:
    with pytest.raises(ValidationError, match="no workflow"):
        credit(in_scope=False)
    assert credit(in_scope=False, workflow=None, expected_eligibility_outcome=None).workflow is None


def test_workflow_paths_start_at_the_scenario_workflow() -> None:
    routing = credit(
        workflow="account_inquiry",
        expected_eligibility_outcome=None,
        expected_workflow_path=[
            "account_inquiry",
            "credit",
        ],
    )
    assert routing.expected_workflow_path == (WorkflowId.ACCOUNT_INQUIRY, WorkflowId.CREDIT)
    with pytest.raises(ValidationError, match="starts with"):
        credit(expected_workflow_path=["credit"])
    with pytest.raises(ValidationError, match="starts with"):
        credit(expected_workflow_path=["dispute", "credit"])


def test_an_expected_eligibility_outcome_needs_a_credit_scenario() -> None:
    with pytest.raises(ValidationError, match="credit scenario"):
        credit(workflow="card_support")


def test_a_1_0_scenario_cannot_carry_1_1_fields() -> None:
    with pytest.raises(ValidationError, match=r"added in 1\.1\.0"):
        credit(schema_version="1.0.0")


def test_credit_approval_claim_names_the_unsafe_claim_graders_detect() -> None:
    """The only allowed ``approv`` word near the credit vocabulary: it is used as a forbidden disclosure."""
    assert DisclosureKind.CREDIT_APPROVAL_CLAIM.value == "credit_approval_claim"
    assert any(item.kind is DisclosureKind.CREDIT_APPROVAL_CLAIM for item in credit().forbidden_disclosures)
