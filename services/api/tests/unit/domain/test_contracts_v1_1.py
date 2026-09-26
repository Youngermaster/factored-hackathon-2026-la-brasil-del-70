"""Version 1.1.0 of the handoff and execution record contracts."""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from bank_agent.domain.base import internal_fields, pii_fields
from bank_agent.domain.cards import CardAction, CardRequest
from bank_agent.domain.eligibility import (
    CreditReview,
    EligibilityAssessmentRecord,
    ReviewReason,
    RiskEstimateRecord,
)
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.handoff import EscalationReason, Handoff, HandoffRecord
from bank_agent.domain.identifiers import ApplicationId, SourceRef
from bank_agent.domain.workflow import WorkflowRef
from bank_agent_builders import eligibility_assessment, execution_record, handoff, handoff_v1_1, risk_estimate

SCHEMAS = Path(__file__).resolve().parents[5] / "contracts" / "schemas"
OUTPUT_CONTRACTS = ("handoff", "execution_record", "decision")


def schema(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((SCHEMAS / f"{name}.v1.json").read_text(encoding="utf-8"))
    return document


def assert_fits_schema(name: str, document: dict[str, Any]) -> None:
    errors = [error.message for error in jsonschema.Draft202012Validator(schema(name)).iter_errors(document)]
    assert errors == []


def review(**overrides: Any) -> CreditReview:
    assessment = eligibility_assessment(outcome="review_required", review_reasons=["borderline_risk_interval"])
    return CreditReview.from_assessment(assessment, estimate=risk_estimate(), **overrides)


def credit_handoff(**overrides: Any) -> Handoff:
    fields: dict[str, Any] = {
        "workflow": WorkflowRef(id="credit", version=1),
        "case_ref": None,
        "actions_taken": [],
        "escalation_reason": EscalationReason(
            code=EscalationReasonCode.CREDIT_REVIEW_REQUIRED, detail="Borderline indicative result."
        ),
        "credit_review": review(application_ref=ApplicationId("app-000001")),
    }
    return handoff_v1_1(**{**fields, **overrides})


def card_handoff(**overrides: Any) -> Handoff:
    fields: dict[str, Any] = {
        "workflow": WorkflowRef(id="card_support", version=1),
        "case_ref": None,
        "actions_taken": [],
        "escalation_reason": EscalationReason(
            code=EscalationReasonCode.CARD_UNBLOCK_REQUESTED, detail="Customer asks to unblock the card."
        ),
        "card_request": CardRequest(
            action=CardAction.UNBLOCK_REQUEST, product_ref=SourceRef.model_validate("products:PRD-A-CARD")
        ),
    }
    return handoff_v1_1(**{**fields, **overrides})


# --- Handoff -------------------------------------------------------------------------------------------------


def test_new_handoffs_are_version_1_1_and_fit_the_schema() -> None:
    for document in (credit_handoff(), card_handoff()):
        assert document.schema_version == "1.1.0"
        assert Handoff.model_validate_json(document.model_dump_json()) == document
        assert_fits_schema("handoff", document.model_dump(mode="json"))


def test_the_model_default_is_1_1_and_the_phase_02_builder_stays_1_0() -> None:
    assert Handoff.model_fields["schema_version"].default == "1.1.0"
    assert handoff().schema_version == "1.0.0"
    assert_fits_schema("handoff", handoff().model_dump(mode="json"))


def test_a_1_0_handoff_cannot_carry_1_1_fields() -> None:
    with pytest.raises(ValidationError, match=r"added in 1\.1\.0"):
        handoff(workflow=WorkflowRef(id="dispute", version=1))
    assert handoff_v1_1(workflow=WorkflowRef(id="dispute", version=1)).workflow is not None


def test_credit_review_codes_need_a_credit_review() -> None:
    with pytest.raises(ValidationError, match="needs a credit_review"):
        credit_handoff(credit_review=None)
    contested = credit_handoff(
        escalation_reason=EscalationReason(code=EscalationReasonCode.ELIGIBILITY_CONTESTED, detail="Contests."),
        credit_review=review(extra_reasons=(ReviewReason.CUSTOMER_CONTESTS_RESULT,)),
    )
    assert contested.credit_review is not None


def test_card_request_codes_need_the_matching_request() -> None:
    with pytest.raises(ValidationError, match="needs a card_request"):
        card_handoff(card_request=None)
    with pytest.raises(ValidationError, match="needs a card_request"):
        card_handoff(
            escalation_reason=EscalationReason(
                code=EscalationReasonCode.CARD_REPLACEMENT_REQUESTED, detail="Customer asks for a new card."
            )
        )


def test_the_risk_estimate_in_a_handoff_is_internal_and_no_personal_data_is_added() -> None:
    assert "handoff.credit_review.risk" in internal_fields(HandoffRecord)
    assert pii_fields(HandoffRecord) == {"resolution.note": "free_text"}


# --- Execution record ----------------------------------------------------------------------------------------


def credit_record(**overrides: Any) -> ExecutionRecord:
    fields: dict[str, Any] = {
        "workflow": WorkflowRef(id="credit", version=1),
        "workflow_before": WorkflowRef(id="account_inquiry", version=1),
        "risk_estimates": [RiskEstimateRecord.from_estimate(risk_estimate(), latency_ms=6)],
        "eligibility_assessments": [EligibilityAssessmentRecord.from_assessment(eligibility_assessment())],
    }
    return execution_record(**{**fields, **overrides})


def test_records_carry_estimates_and_assessments_separately() -> None:
    record = credit_record()
    assert record.schema_version == "1.1.0"
    assert ExecutionRecord.model_validate_json(record.model_dump_json()) == record
    assert_fits_schema("execution_record", record.model_dump(mode="json"))
    assert "risk_estimates" in internal_fields(ExecutionRecord)
    assert "eligibility_assessments" not in internal_fields(ExecutionRecord)


def test_workflow_before_marks_a_real_move() -> None:
    with pytest.raises(ValidationError, match="another workflow"):
        credit_record(workflow_before=WorkflowRef(id="credit", version=1))


def test_estimates_and_assessments_are_recorded_once() -> None:
    estimate = RiskEstimateRecord.from_estimate(risk_estimate(), latency_ms=6)
    with pytest.raises(ValidationError, match="once each"):
        credit_record(risk_estimates=[estimate, estimate])


def test_a_1_0_record_cannot_carry_1_1_fields() -> None:
    with pytest.raises(ValidationError, match=r"added in 1\.1\.0"):
        credit_record(schema_version="1.0.0")
    assert execution_record(schema_version="1.0.0").schema_version == "1.0.0"


# --- Schemas -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", OUTPUT_CONTRACTS)
def test_only_fields_added_in_a_minor_version_are_optional_in_output_schemas(name: str) -> None:
    document = schema(name)
    added = {key for key, value in document["properties"].items() if "x-added-in" in value}
    required = set(document.get("required", []))
    assert not added & required
    assert required | added == set(document["properties"])
    for definition in document.get("$defs", {}).values():
        for key, value in definition.get("properties", {}).items():
            if "x-added-in" in value:
                assert key not in definition.get("required", [])


def test_the_new_top_level_fields_are_marked() -> None:
    handoff_added = {k for k, v in schema("handoff")["properties"].items() if "x-added-in" in v}
    record_added = {k for k, v in schema("execution_record")["properties"].items() if "x-added-in" in v}
    assert handoff_added == {"workflow", "credit_review", "card_request"}
    assert record_added == {"workflow_before", "risk_estimates", "eligibility_assessments"}
