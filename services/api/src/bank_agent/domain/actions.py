"""Actions the workflow can take, tool names, and the verification of outcomes.

Action arguments never contain a customer identifier: the session context supplies it. An action counts as
done only when a ``Verification`` read back its effect and found the expected state.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, PositiveInt, model_validator

from bank_agent.domain.base import Code, DomainModel, UtcDatetime
from bank_agent.domain.cards import CardBlockReason
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.identifiers import IdempotencyKey, ProductId, SourceRef, TransactionId
from bank_agent.domain.money import Money
from bank_agent.domain.workflow import StateName


class ActionKind(StrEnum):
    CREATE_DISPUTE_CASE = "create_dispute_case"
    BLOCK_CARD = "block_card"


class ToolName(StrEnum):
    """Every banking tool (phase 05). The last two are writes and match ``ActionKind``."""

    LIST_RECENT_TRANSACTIONS = "list_recent_transactions"
    GET_TRANSACTION = "get_transaction"
    GET_PRODUCT_STATUS = "get_product_status"
    LIST_MY_CASES = "list_my_cases"
    GET_CASE_STATUS = "get_case_status"
    CREATE_DISPUTE_CASE = "create_dispute_case"
    BLOCK_CARD = "block_card"


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


ActionArguments = Annotated[CreateDisputeArguments | BlockCardArguments, Field(discriminator="action")]


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
