"""What the credit workflow keeps between turns (``WorkflowPosition.data["flow"]``).

The customer's own request (product, amount, term, purpose, and an income they declared) and the synthetic
eligibility service's assessment, which carries rule ids, reasons, and review flags but no profile value and no
estimate value. The credit profile and the risk estimate are never kept here: they live for one turn only.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, JsonValue

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.data import dump
from bank_agent.application.engine.shared import spend_clarification
from bank_agent.domain.base import DomainModel
from bank_agent.domain.credit import CreditProductType, TermMonths
from bank_agent.domain.eligibility import EligibilityAssessment, EligibilityOutcome
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import Intent

CARD_TERM_MONTHS = 1
"""A credit card has no term: an intake records one month, the billing cycle and every card's catalog minimum."""
DEFAULT_PURPOSE = "general_purpose"


class Offer(StrEnum):
    NONE = "none"
    INTAKE = "intake"
    REVIEW_HANDOFF = "review_handoff"
    CONTACT = "contact"


class CreditData(DomainModel):
    intent: Intent | None = None
    product_type: CreditProductType | None = None
    product_code: CreditProductCode | None = None
    amount: Annotated[Decimal, Field(gt=0)] | None = None
    currency: Currency | None = None
    term_months: TermMonths | None = None
    purpose: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")] | None = None
    declared_income: Money | None = None
    listed: bool = False
    detailed: bool = False
    asked_facts: bool = False
    choosing_product: bool = False
    assessment: EligibilityAssessment | None = None
    explained: bool = False
    offer: Offer = Offer.NONE
    intake_shown: bool = False

    def term_for(self, product_type: CreditProductType) -> int | None:
        return CARD_TERM_MONTHS if product_type is CreditProductType.CREDIT_CARD else self.term_months


def load(ctx: TurnContext) -> CreditData:
    return CreditData.model_validate(ctx.flow) if ctx.flow else CreditData()


def save(ctx: TurnContext, data: CreditData) -> None:
    flow: dict[str, JsonValue] = dump(data)
    ctx.flow = flow


def open_questions(data: CreditData) -> tuple[str, ...]:
    questions: list[str] = []
    if data.intent in (Intent.CREDIT_ELIGIBILITY, Intent.CREDIT_APPLICATION):
        if data.product_type is None:
            questions.append("Which credit product does the customer want?")
        if data.amount is None:
            questions.append("What amount does the customer ask for?")
        if data.product_type is CreditProductType.PERSONAL_LOAN and data.term_months is None:
            questions.append("What term does the customer want?")
    if data.assessment is not None and data.assessment.missing_facts:
        questions.append("Which missing information can the customer or the records provide?")
    elif data.assessment is not None and data.assessment.outcome is not EligibilityOutcome.INDICATIVELY_ELIGIBLE:
        questions.append("What does the credit team conclude after reviewing the flagged request?")
    return tuple(questions)


def exhausted(ctx: TurnContext, data: CreditData) -> Step | None:
    """The escalation when no clarifying question is left, else ``None`` (and one more question is counted)."""
    save(ctx, data)
    return spend_clarification(ctx, open_questions=open_questions(data))
