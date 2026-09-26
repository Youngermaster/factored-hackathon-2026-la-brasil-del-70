import pytest
from pydantic import ValidationError

from bank_agent.domain.actions import (
    ActionKind,
    ActionRequest,
    ActionResult,
    ActionStatus,
    BlockCardArguments,
    CreateDisputeArguments,
    Verification,
)
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.identifiers import IdempotencyKey, ProductId, SourceRef, TransactionId
from bank_agent.domain.money import Currency, Money
from bank_agent_builders import T0

KEY = IdempotencyKey("idem-key-fixture-0001")
CARD = ProductId("PRD-A-CARD")
CARD_REF = SourceRef.model_validate("products:PRD-A-CARD")


def test_action_arguments_are_discriminated_by_action() -> None:
    request = ActionRequest.model_validate(
        {
            "action": "block_card",
            "target": "products:PRD-A-CARD",
            "arguments": {"action": "block_card", "product_id": "PRD-A-CARD"},
            "idempotency_key": KEY,
            "requested_in_state": "EXECUTE",
        }
    )
    assert isinstance(request.arguments, BlockCardArguments)


def test_rejects_arguments_for_another_action() -> None:
    with pytest.raises(ValidationError):
        ActionRequest(
            action=ActionKind.CREATE_DISPUTE_CASE,
            target=CARD_REF,
            arguments=BlockCardArguments(product_id=CARD),
            idempotency_key=KEY,
            requested_in_state="EXECUTE",
        )


def test_action_arguments_never_carry_a_customer_id() -> None:
    for model in (CreateDisputeArguments, BlockCardArguments, ActionRequest):
        assert not any("customer" in name for name in model.model_fields)


def test_create_dispute_arguments() -> None:
    arguments = CreateDisputeArguments(
        transaction_id=TransactionId("TXN-1"),
        reason=DisputeReason.DUPLICATE,
        disputed_amount=Money.of("10", Currency.MXN),
    )
    assert arguments.action is ActionKind.CREATE_DISPUTE_CASE


def test_result_error_code_matches_status() -> None:
    ok = ActionResult(
        action=ActionKind.BLOCK_CARD, idempotency_key=KEY, status=ActionStatus.EXECUTED, attempts=1, completed_at=T0
    )
    assert ok.error_code is None
    with pytest.raises(ValidationError):
        ActionResult(
            action=ActionKind.BLOCK_CARD, idempotency_key=KEY, status=ActionStatus.UNKNOWN, attempts=1, completed_at=T0
        )
    with pytest.raises(ValidationError):
        ActionResult(
            action=ActionKind.BLOCK_CARD,
            idempotency_key=KEY,
            status=ActionStatus.EXECUTED,
            error_code="timeout",
            attempts=1,
            completed_at=T0,
        )


def test_positive_verification_needs_evidence_and_negative_needs_a_mismatch_code() -> None:
    assert Verification(
        verified=True,
        check="case_matches_request",
        evidence=SourceRef.model_validate("dispute_cases:c-1"),
        checked_at=T0,
    )
    with pytest.raises(ValidationError):
        Verification(verified=True, check="case_matches_request", checked_at=T0)
    with pytest.raises(ValidationError):
        Verification(verified=False, check="case_matches_request", checked_at=T0)
    assert Verification(verified=False, check="case_matches_request", mismatch_code="not_found", checked_at=T0)
