"""What the account inquiry workflow keeps between turns (``WorkflowPosition.data["flow"]``).

Only slots the customer gave and identifiers of the customer's own records: no balance or amount read from a record
is kept here (answers read them again).
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, JsonValue

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.data import dump
from bank_agent.application.engine.shared import spend_clarification
from bank_agent.domain.base import DomainModel, UntrustedText
from bank_agent.domain.identifiers import ProductId, TransactionId
from bank_agent.domain.intelligence import DateRange, TransactionDescriptor
from bank_agent.domain.money import Currency
from bank_agent.domain.product import ProductType
from bank_agent.domain.workflow import Intent


class Choosing(StrEnum):
    NOTHING = "nothing"
    PRODUCT = "product"
    PAYMENT = "payment"
    PAYMENT_DETAILS = "payment_details"


class AccountData(DomainModel):
    intent: Intent | None = None
    hint_type: ProductType | None = None
    hint_last4: Annotated[str, Field(pattern=r"^[0-9]{4}$")] | None = None
    product_id: ProductId | None = None
    choosing: Choosing = Choosing.NOTHING
    option_ids: tuple[str, ...] = ()
    period_expression: Annotated[str, Field(max_length=100)] | None = None
    period_start: date | None = None
    period_end: date | None = None
    asked_period: bool = False
    amount: Annotated[Decimal, Field(ge=0)] | None = None
    currency: Currency | None = None
    payee: Annotated[str, Field(max_length=150)] | None = None
    date_expression: Annotated[str, Field(max_length=100)] | None = None
    date_options: Annotated[tuple[DateRange, ...], Field(max_length=4)] = ()
    transaction_id: TransactionId | None = None
    answered: bool = False

    def period(self) -> DateRange | None:
        if self.period_start is None or self.period_end is None:
            return None
        return DateRange(start=self.period_start, end=self.period_end)

    def descriptor(self) -> TransactionDescriptor:
        return TransactionDescriptor(
            amount=self.amount,
            currency_hint=self.currency,
            merchant_text=UntrustedText(self.payee) if self.payee else None,
            date_expression=UntrustedText(self.date_expression) if self.date_expression else None,
            date_interpretations=self.date_options,
            card_last4_hint=self.hint_last4,
        )


def load(ctx: TurnContext) -> AccountData:
    return AccountData.model_validate(ctx.flow) if ctx.flow else AccountData()


def save(ctx: TurnContext, data: AccountData) -> None:
    flow: dict[str, JsonValue] = dump(data)
    ctx.flow = flow


def open_questions(data: AccountData) -> tuple[str, ...]:
    questions: list[str] = []
    if data.intent is Intent.STATEMENT_REQUEST and data.product_id is None:
        questions.append("Which product does the customer mean?")
    if data.intent is Intent.STATEMENT_REQUEST and data.period() is None:
        questions.append("Which statement period does the customer want?")
    if data.intent is Intent.PAYMENT_STATUS and data.transaction_id is None:
        questions.append("Which payment or transfer does the customer mean?")
    return tuple(questions)


def exhausted(ctx: TurnContext, data: AccountData) -> Step | None:
    """The escalation when no clarifying question is left, else ``None`` (and one more question is counted)."""
    save(ctx, data)
    return spend_clarification(ctx, open_questions=open_questions(data))
