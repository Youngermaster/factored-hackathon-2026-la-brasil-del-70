from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from bank_agent.domain.actions import ActionKind, ActionRequest, BlockCardArguments
from bank_agent.domain.cards import (
    ESCALATION_ONLY_CARD_ACTIONS,
    SELF_SERVICE_CARD_ACTIONS,
    CardAction,
    CardBlockReason,
    CardRequest,
    CardStatusView,
)
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.identifiers import ProductId, SourceRef
from bank_agent.domain.product import ProductStatus, ProductType
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import CARD_ACTION_HANDLING, CardActionHandling, CardActionHandlingKind
from bank_agent_builders import idempotency_key, product


def test_every_card_action_is_either_self_service_or_escalation_only() -> None:
    assert set(CARD_ACTION_HANDLING) == set(CardAction)
    assert set(CardAction) == SELF_SERVICE_CARD_ACTIONS | ESCALATION_ONLY_CARD_ACTIONS
    assert not SELF_SERVICE_CARD_ACTIONS & ESCALATION_ONLY_CARD_ACTIONS


def test_block_is_a_verified_self_service_write_in_card_support_and_dispute() -> None:
    block = CARD_ACTION_HANDLING[CardAction.BLOCK]
    assert block.kind is CardActionHandlingKind.SELF_SERVICE
    assert block.write_action is ActionKind.BLOCK_CARD
    assert (block.requires_confirmation, block.requires_step_up, block.verified_read_back) == (True, True, True)
    assert set(block.workflows) == {WorkflowId.CARD_SUPPORT, WorkflowId.DISPUTE}


@pytest.mark.parametrize(
    ("action", "code"),
    [
        (CardAction.UNBLOCK_REQUEST, EscalationReasonCode.CARD_UNBLOCK_REQUESTED),
        (CardAction.REPLACEMENT_REQUEST, EscalationReasonCode.CARD_REPLACEMENT_REQUESTED),
    ],
)
def test_unblock_and_replacement_are_escalation_only(action: CardAction, code: EscalationReasonCode) -> None:
    handling = CARD_ACTION_HANDLING[action]
    assert handling.kind is CardActionHandlingKind.ESCALATION_ONLY
    assert handling.write_action is None
    assert handling.escalation_code is code
    assert not handling.requires_confirmation


def _handling(**overrides: Any) -> CardActionHandling:
    fields: dict[str, Any] = {
        "action": CardAction.BLOCK,
        "kind": CardActionHandlingKind.SELF_SERVICE,
        "write_action": ActionKind.BLOCK_CARD,
        "requires_confirmation": True,
        "requires_step_up": True,
        "verified_read_back": True,
        "workflows": [WorkflowId.CARD_SUPPORT],
    }
    return CardActionHandling.model_validate({**fields, **overrides})


def test_handling_rows_are_validated() -> None:
    with pytest.raises(ValidationError, match="needs a write action"):
        _handling(write_action=None)
    with pytest.raises(ValidationError, match="no escalation code"):
        _handling(escalation_code=EscalationReasonCode.OTHER)
    with pytest.raises(ValidationError, match="step-up"):
        _handling(requires_step_up=False)
    with pytest.raises(ValidationError, match="needs an escalation code"):
        _handling(kind=CardActionHandlingKind.ESCALATION_ONLY, write_action=None)
    with pytest.raises(ValidationError, match="no tool"):
        _handling(
            action=CardAction.UNBLOCK_REQUEST,
            kind=CardActionHandlingKind.ESCALATION_ONLY,
            escalation_code=EscalationReasonCode.CARD_UNBLOCK_REQUESTED,
        )


def test_card_status_view_from_a_card() -> None:
    view = CardStatusView.from_product(product(expires_on=date(2028, 3, 31), status=ProductStatus.BLOCKED))
    assert view.status is ProductStatus.BLOCKED
    assert view.expires_on == date(2028, 3, 31)
    assert str(view.masked_number) == "**** 1234"


def test_card_status_view_is_for_cards_only() -> None:
    with pytest.raises(ValidationError, match="credit and debit cards"):
        CardStatusView.from_product(product(product_type=ProductType.SAVINGS_ACCOUNT))


def test_card_references_point_to_products() -> None:
    with pytest.raises(ValidationError, match="products table"):
        CardRequest(action=CardAction.UNBLOCK_REQUEST, product_ref=SourceRef.model_validate("transactions:T1"))
    request = CardRequest(action=CardAction.REPLACEMENT_REQUEST, product_ref=SourceRef.model_validate("products:P1"))
    assert request.action is CardAction.REPLACEMENT_REQUEST


def test_block_arguments_take_an_optional_reason() -> None:
    assert BlockCardArguments(product_id=ProductId("P1")).reason is None
    request = ActionRequest.model_validate(
        {
            "action": "block_card",
            "target": "products:P1",
            "arguments": {"action": "block_card", "product_id": "P1", "reason": "stolen"},
            "idempotency_key": idempotency_key(),
            "requested_in_state": "CONFIRM_BLOCK",
        }
    )
    assert isinstance(request.arguments, BlockCardArguments)
    assert request.arguments.reason is CardBlockReason.STOLEN
