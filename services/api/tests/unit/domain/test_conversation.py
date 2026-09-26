from datetime import timedelta

import pytest
from pydantic import ValidationError

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.base import pii_fields
from bank_agent.domain.conversation import (
    ActionDisplayStatus,
    ActionStatusView,
    AssistantResponse,
    Clarification,
    ClarificationOption,
    ConfirmationCard,
    Turn,
    TurnResult,
)
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.identifiers import ConversationId, SourceRef, TurnId
from bank_agent.domain.locale import Language
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import Outcome
from bank_agent_builders import T0, a_date, conversation, turn


def test_turn_text_is_marked_personal_and_capped() -> None:
    assert pii_fields(Turn) == {"customer_text": "free_text"}
    with pytest.raises(ValidationError):
        turn(text="x" * 2001)


def test_a_completed_turn_has_a_response_and_completion_time() -> None:
    response = AssistantResponse(language=Language.ES, text="Hola")
    with pytest.raises(ValidationError):
        turn().evolve(response=response)
    completed = turn().evolve(response=response, completed_at=T0 + timedelta(seconds=1))
    assert completed.response == response
    with pytest.raises(ValidationError):
        turn().evolve(response=response, completed_at=T0 - timedelta(seconds=1))


def test_conversation_rejects_update_before_creation() -> None:
    with pytest.raises(ValidationError):
        conversation().evolve(updated_at=T0 - timedelta(seconds=1))


def test_an_action_is_shown_verified_only_with_evidence() -> None:
    with pytest.raises(ValidationError):
        ActionStatusView(action=ActionKind.CREATE_DISPUTE_CASE, status=ActionDisplayStatus.VERIFIED)
    view = ActionStatusView(
        action=ActionKind.CREATE_DISPUTE_CASE,
        status=ActionDisplayStatus.VERIFIED,
        reference=SourceRef.model_validate("dispute_cases:case-1"),
        evidence=SourceRef.model_validate("dispute_cases:case-1"),
    )
    assert view.evidence is not None


def test_response_carries_every_message_variant() -> None:
    amount = Money.of("1250.00", Currency.MXN)
    response = AssistantResponse(
        language=Language.PT,
        text="Qual destas compras?",
        clarification=Clarification(
            options=(ClarificationOption(option_id="opt-1", occurred_on=a_date(), amount=amount, card_last4="1234"),)
        ),
        confirmation=ConfirmationCard(
            occurred_on=a_date(),
            amount=amount,
            reason=DisputeReason.UNRECOGNIZED,
            planned_actions=(ActionKind.CREATE_DISPUTE_CASE, ActionKind.BLOCK_CARD),
        ),
        step_up_required=True,
    )
    result = TurnResult(
        turn_id=TurnId("turn-1"),
        conversation_id=ConversationId("conv-1"),
        state="CLARIFY",
        outcome=Outcome.CLARIFIED,
        response=response,
    )
    assert TurnResult.model_validate_json(result.model_dump_json()) == result


def test_clarification_offers_at_most_three_options() -> None:
    option = ClarificationOption(option_id="opt-1", occurred_on=a_date(), amount=Money.of("1", Currency.MXN))
    with pytest.raises(ValidationError):
        Clarification(options=(option,) * 4)
