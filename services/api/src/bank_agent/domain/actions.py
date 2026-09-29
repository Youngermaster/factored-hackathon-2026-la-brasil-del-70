"""Actions the workflow can take, tool names, and the verification of outcomes.

Action arguments never contain a customer identifier: the session context supplies it. An action counts as
done only when a ``Verification`` read back its effect and found the expected state.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, PositiveInt, StringConstraints, model_validator

from bank_agent.domain.base import Code, DomainModel, Pii, UtcDatetime
from bank_agent.domain.cards import CardBlockReason
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.identifiers import (
    AssessmentId,
    ConversationId,
    CreditProductCode,
    IdempotencyKey,
    ProductId,
    SourceRef,
    TransactionId,
)
from bank_agent.domain.money import Money
from bank_agent.domain.workflow import StateName


class ActionKind(StrEnum):
    CREATE_DISPUTE_CASE = "create_dispute_case"
    BLOCK_CARD = "block_card"
    SUBMIT_CREDIT_APPLICATION = "submit_credit_application"
    """Records an application intake for human review. It never decides and never moves money."""


class ToolName(StrEnum):
    """Every banking tool (phase 05).

    Three are writes and share their value with an ``ActionKind``: ``create_dispute_case``, ``block_card``, and
    ``submit_credit_application``. Every other tool reads. ``get_product_status`` also serves card status, and
    ``list_my_cards`` lists the customer's cards so the card workflow can offer a masked choice, and
    ``list_my_credit_applications`` lists their credit application intakes so a status question needs no id. The
    risk estimator and the eligibility service are not tools: the engine calls them, and no model output can
    select them.
    """

    LIST_RECENT_TRANSACTIONS = "list_recent_transactions"
    GET_TRANSACTION = "get_transaction"
    GET_PRODUCT_STATUS = "get_product_status"
    LIST_MY_CARDS = "list_my_cards"
    """The session customer's credit and debit cards with status and expiry (added in 1.2.0)."""
    LIST_MY_CASES = "list_my_cases"
    GET_CASE_STATUS = "get_case_status"
    CREATE_DISPUTE_CASE = "create_dispute_case"
    BLOCK_CARD = "block_card"
    LIST_MY_BALANCES = "list_my_balances"
    GET_PAYMENT_STATUS = "get_payment_status"
    GET_STATEMENT_SUMMARY = "get_statement_summary"
    LIST_CREDIT_PRODUCTS = "list_credit_products"
    GET_CREDIT_PRODUCT = "get_credit_product"
    GET_MY_CREDIT_PROFILE = "get_my_credit_profile"
    SUBMIT_CREDIT_APPLICATION = "submit_credit_application"
    GET_CREDIT_APPLICATION_STATUS = "get_credit_application_status"
    LIST_MY_CREDIT_APPLICATIONS = "list_my_credit_applications"
    """The session customer's credit application intakes, newest first (added in 1.3.0)."""


WRITE_TOOLS = frozenset({ToolName.CREATE_DISPUTE_CASE, ToolName.BLOCK_CARD, ToolName.SUBMIT_CREDIT_APPLICATION})


class ToolFailureMode(StrEnum):
    """Failure modes the test-only ``ToolFailureInjector`` (phase 05) and evaluation scenarios use."""

    TIMEOUT = "timeout"
    TRANSIENT_ERROR = "transient_error"
    PERMANENT_ERROR = "permanent_error"
    PARTIAL_WRITE = "partial_write"


class CreateDisputeArguments(DomainModel):
    action: Literal[ActionKind.CREATE_DISPUTE_CASE] = ActionKind.CREATE_DISPUTE_CASE
    transaction_id: TransactionId
    reason: DisputeReason
    disputed_amount: Money


class BlockCardArguments(DomainModel):
    action: Literal[ActionKind.BLOCK_CARD] = ActionKind.BLOCK_CARD
    product_id: ProductId
    reason: CardBlockReason | None = None


class SubmitCreditApplicationArguments(DomainModel):
    """What the customer asks for. The purpose is a code the catalog entry must allow (checked by policy).

    ``assessment_ref`` and ``origin_conversation_id`` link the intake to the eligibility assessment the customer
    confirmed after and to the conversation it came from, so an agent reviews both. The engine sets them from its
    own state, never from model output; neither identifies a customer.
    """

    action: Literal[ActionKind.SUBMIT_CREDIT_APPLICATION] = ActionKind.SUBMIT_CREDIT_APPLICATION
    product_code: CreditProductCode
    requested_amount: Money
    requested_term_months: Annotated[int, Field(ge=1, le=480)]
    purpose: Code
    declared_monthly_income: Annotated[Money | None, Pii("financial")] = None
    assessment_ref: AssessmentId | None = None
    origin_conversation_id: ConversationId | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.requested_amount.amount <= 0:
            raise ValueError("the requested amount must be positive")
        income = self.declared_monthly_income
        if income is not None and (income.amount < 0 or income.currency is not self.requested_amount.currency):
            raise ValueError("declared income must be non-negative and in the requested currency")
        return self


ActionArguments = Annotated[
    CreateDisputeArguments | BlockCardArguments | SubmitCreditApplicationArguments, Field(discriminator="action")
]


class ActionRequest(DomainModel):
    action: ActionKind
    target: SourceRef
    arguments: ActionArguments
    idempotency_key: IdempotencyKey
    requested_in_state: StateName
    confirmed_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _validate_arguments(self) -> Self:
        if self.arguments.action is not self.action:
            raise ValueError("the arguments must match the action")
        return self


class ActionStatus(StrEnum):
    EXECUTED = "executed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ActionResult(DomainModel):
    action: ActionKind
    idempotency_key: IdempotencyKey
    status: ActionStatus
    error_code: Code | None = None
    outcome_ref: SourceRef | None = None
    attempts: PositiveInt
    completed_at: UtcDatetime

    @model_validator(mode="after")
    def _validate_error(self) -> Self:
        if self.status is ActionStatus.EXECUTED and self.error_code is not None:
            raise ValueError("an executed action has no error code")
        if self.status is not ActionStatus.EXECUTED and self.error_code is None:
            raise ValueError("a failed or unknown action needs an error code")
        return self


class Verification(DomainModel):
    """The result of reading back an action's effect."""

    verified: bool
    check: Code
    evidence: SourceRef | None = None
    mismatch_code: Code | None = None
    checked_at: UtcDatetime

    @model_validator(mode="after")
    def _validate_evidence(self) -> Self:
        if self.verified and (self.evidence is None or self.mismatch_code is not None):
            raise ValueError("a positive verification needs evidence and no mismatch code")
        if not self.verified and self.mismatch_code is None:
            raise ValueError("a negative verification needs a mismatch code")
        return self


class ActionLedgerEntry(DomainModel):
    """The first outcome of a write that has no natural idempotency record of its own (a card block).

    A repeated idempotency key with the same ``request_digest`` replays ``outcome``; with a different digest it is
    an idempotency conflict. The entry belongs to the context customer, never named here.
    """

    action: ActionKind
    idempotency_key: IdempotencyKey
    target: SourceRef
    request_digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    outcome: Code
    recorded_at: UtcDatetime
