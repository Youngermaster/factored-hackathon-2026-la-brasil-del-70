"""What the dispute workflow keeps between turns (``WorkflowPosition.data["flow"]``)."""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, JsonValue

from bank_agent.application.engine.context import TurnContext
from bank_agent.application.engine.data import dump
from bank_agent.domain.base import DomainModel, UntrustedText
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.identifiers import CaseId, ProductId, TransactionId
from bank_agent.domain.intelligence import DateRange, TransactionDescriptor
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.transaction import TransactionChannel
from bank_agent.domain.workflow import Intent


class BlockOffer(StrEnum):
    NONE = "none"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    SKIPPED = "skipped"


class DisputeData(DomainModel):
    intent: Intent | None = None
    amount: Annotated[Decimal, Field(ge=0)] | None = None
    currency: Currency | None = None
    merchant: Annotated[str, Field(max_length=150)] | None = None
    date_expression: Annotated[str, Field(max_length=100)] | None = None
    date_options: Annotated[tuple[DateRange, ...], Field(max_length=4)] = ()
    channel: TransactionChannel | None = None
    card_last4: Annotated[str, Field(pattern=r"^[0-9]{4}$")] | None = None
    reason: DisputeReason | None = None
    asked_reason: bool = False
    asked_details: bool = False
    asked_date: bool = False
    option_ids: tuple[TransactionId, ...] = ()
    transaction_id: TransactionId | None = None
    product_id: ProductId | None = None
    product_last4: Annotated[str, Field(pattern=r"^[0-9A-Z]{4}$")] | None = None
    card_active: bool = False
    disputed_amount: Money | None = None
    block_offer: BlockOffer = BlockOffer.NONE
    summary_shown: bool = False
    case_id: CaseId | None = None

    def descriptor(self) -> TransactionDescriptor:
        return TransactionDescriptor(
            amount=self.amount,
            currency_hint=self.currency,
            merchant_text=UntrustedText(self.merchant) if self.merchant else None,
            date_expression=UntrustedText(self.date_expression) if self.date_expression else None,
            date_interpretations=self.date_options,
            channel_hint=self.channel,
            card_last4_hint=self.card_last4,
        )


def load(ctx: TurnContext) -> DisputeData:
    return DisputeData.model_validate(ctx.flow) if ctx.flow else DisputeData()


def save(ctx: TurnContext, data: DisputeData) -> None:
    flow: dict[str, JsonValue] = dump(data)
    ctx.flow = flow


def open_questions(data: DisputeData) -> tuple[str, ...]:
    questions: list[str] = []
    if data.transaction_id is None:
        questions.append("Which transaction does the customer dispute?")
    if data.reason is None:
        questions.append("What is the reason for the dispute?")
    if data.date_expression is not None and len(data.date_options) > 1:
        questions.append("Which date did the customer mean?")
    return tuple(questions)
