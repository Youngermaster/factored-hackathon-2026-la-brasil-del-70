from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from bank_agent.domain.accounts import BalanceView, PaymentStatusView, StatementPeriod, StatementSummary
from bank_agent.domain.actions import ActionKind, ActionRequest, SubmitCreditApplicationArguments
from bank_agent.domain.base import pii_fields
from bank_agent.domain.cards import CardAction, CardBlockReason, CardStatusView
from bank_agent.domain.conversation import (
    AssistantResponse,
    CardActionConfirmation,
    ConfirmationCard,
    CreditIntakeConfirmation,
    Turn,
)
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.eligibility import EligibilityOutcome, EligibilityView
from bank_agent.domain.identifiers import CreditProductCode, SourceRef
from bank_agent.domain.intelligence import DateRange
from bank_agent.domain.locale import Language
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.transaction import TransactionType
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_agent_builders import T0, a_date, eligibility_assessment, idempotency_key, product, transaction

MXN = Currency.MXN


def mxn(amount: str) -> Money:
    return Money.of(amount, MXN)


def card_confirmation(**overrides: Any) -> CardActionConfirmation:
    fields: dict[str, Any] = {
        "action": CardAction.BLOCK,
        "card_last4": "1234",
        "reason": CardBlockReason.LOST,
        "planned_actions": [ActionKind.BLOCK_CARD],
    }
    return CardActionConfirmation.model_validate({**fields, **overrides})


def intake_confirmation(**overrides: Any) -> CreditIntakeConfirmation:
    fields: dict[str, Any] = {
        "product_code": "MX-PL-FIXTURE",
        "product_type": CreditProductType.PERSONAL_LOAN,
        "requested_amount": mxn("40000"),
        "requested_term_months": 24,
        "purpose": "debt_consolidation",
        "eligibility_outcome": EligibilityOutcome.INDICATIVELY_ELIGIBLE,
        "planned_actions": [ActionKind.SUBMIT_CREDIT_APPLICATION],
    }
    return CreditIntakeConfirmation.model_validate({**fields, **overrides})


def dispute_confirmation() -> ConfirmationCard:
    return ConfirmationCard(
        occurred_on=a_date(),
        amount=mxn("1250.00"),
        reason=DisputeReason.UNRECOGNIZED,
        planned_actions=(ActionKind.CREATE_DISPUTE_CASE,),
    )


def test_a_response_carries_every_new_part_and_round_trips() -> None:
    card = product(current_balance=mxn("8450.00"), credit_limit=mxn("20000.00"), balance_as_of=T0)
    payment = transaction(transaction_type=TransactionType.PAYMENT)
    period = StatementPeriod(
        product_ref=SourceRef.model_validate("products:PRD-A-CARD"),
        dates=DateRange(start=date(2026, 6, 1), end=date(2026, 6, 30)),
    )
    response = AssistantResponse(
        language=Language.ES,
        text="Saldo al 31 de mayo.",
        balances=(BalanceView.from_product(card),),
        payment_statuses=(PaymentStatusView.from_transaction(payment, card, occurred_on=a_date()),),
        statement=StatementSummary.from_transactions(
            period, card, [payment], as_of=T0, local_date=lambda at: at.astimezone(UTC).date()
        ),
        card_status=(CardStatusView.from_product(card),),
        eligibility=EligibilityView.from_assessment(eligibility_assessment()),
        credit_intake_confirmation=intake_confirmation(),
    )
    assert AssistantResponse.model_validate_json(response.model_dump_json()) == response


def test_a_response_asks_for_at_most_one_confirmation() -> None:
    base: dict[str, Any] = {"language": Language.PT, "text": "Confirma?"}
    assert AssistantResponse(**base, confirmation=dispute_confirmation()).confirmation is not None
    assert AssistantResponse(**base, card_action_confirmation=card_confirmation()) is not None
    with pytest.raises(ValidationError, match="at most one confirmation"):
        AssistantResponse(**base, confirmation=dispute_confirmation(), card_action_confirmation=card_confirmation())
    with pytest.raises(ValidationError, match="at most one confirmation"):
        AssistantResponse(
            **base, card_action_confirmation=card_confirmation(), credit_intake_confirmation=intake_confirmation()
        )


def test_new_response_parts_add_no_personal_data_to_turns() -> None:
    assert pii_fields(Turn) == {"customer_text": "free_text"}


def test_card_confirmation_is_only_for_self_service_actions() -> None:
    with pytest.raises(ValidationError, match="go to a human"):
        card_confirmation(action=CardAction.UNBLOCK_REQUEST)
    with pytest.raises(ValidationError, match="block_card"):
        card_confirmation(planned_actions=[ActionKind.CREATE_DISPUTE_CASE])


def test_intake_confirmation_plans_the_intake_and_shows_no_income() -> None:
    assert intake_confirmation().disclaimer == "indicative_not_an_offer_or_decision"
    assert "declared_monthly_income" not in CreditIntakeConfirmation.model_fields
    with pytest.raises(ValidationError, match="submit_credit_application"):
        intake_confirmation(planned_actions=[ActionKind.BLOCK_CARD])


def test_submit_credit_application_arguments() -> None:
    request = ActionRequest.model_validate(
        {
            "action": "submit_credit_application",
            "target": "credit_products:MX-PL-FIXTURE",
            "arguments": {
                "action": "submit_credit_application",
                "product_code": "MX-PL-FIXTURE",
                "requested_amount": {"amount": "40000.00", "currency": "MXN"},
                "requested_term_months": 24,
                "purpose": "debt_consolidation",
            },
            "idempotency_key": idempotency_key(),
            "requested_in_state": "CONFIRM_INTAKE",
        }
    )
    assert isinstance(request.arguments, SubmitCreditApplicationArguments)
    assert request.arguments.product_code == CreditProductCode("MX-PL-FIXTURE")
    with pytest.raises(ValidationError, match="positive"):
        SubmitCreditApplicationArguments(
            product_code=CreditProductCode("MX-PL-FIXTURE"),
            requested_amount=mxn("0"),
            requested_term_months=12,
            purpose="travel",
        )
    with pytest.raises(ValidationError, match="declared income"):
        SubmitCreditApplicationArguments(
            product_code=CreditProductCode("MX-PL-FIXTURE"),
            requested_amount=mxn("10"),
            requested_term_months=12,
            purpose="travel",
            declared_monthly_income=Money.of(Decimal(10), Currency.USD),
        )


def test_the_credit_workflow_may_record_an_intake() -> None:
    assert WORKFLOW_CATALOG.descriptor(WorkflowId.CREDIT).write_actions == (ActionKind.SUBMIT_CREDIT_APPLICATION,)
    assert datetime(2026, 1, 1, tzinfo=UTC) < T0
