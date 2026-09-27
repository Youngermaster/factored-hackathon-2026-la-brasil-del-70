"""Dispute cases and their lifecycle.

The lifecycle (approved with the phase 02 plan):

- ``opened`` -> ``in_review``, ``escalated``, ``rejected``
- ``in_review`` -> ``resolved``, ``rejected``, ``escalated``
- ``escalated`` -> ``in_review``, ``resolved``, ``rejected``
- ``resolved`` and ``rejected`` are terminal.

There is no direct ``opened`` -> ``resolved``: a person or a later review step always moves the case through
``in_review`` or ``escalated``.
"""

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import NonNegativeInt, model_validator

from bank_agent.domain.base import Code, DomainModel, UtcDatetime
from bank_agent.domain.errors import InvalidCaseTransitionError
from bank_agent.domain.identifiers import CaseId, ConversationId, CustomerId, IdempotencyKey, ProductId, TransactionId
from bank_agent.domain.money import Money
from bank_agent.domain.transaction import Transaction


class DisputeReason(StrEnum):
    UNRECOGNIZED = "unrecognized"
    DUPLICATE = "duplicate"
    WRONG_AMOUNT = "wrong_amount"
    NOT_RECEIVED = "not_received"
    ATM_CASH_NOT_DISPENSED = "atm_cash_not_dispensed"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    OTHER = "other"


class DisputeStatus(StrEnum):
    OPENED = "opened"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


ALLOWED_TRANSITIONS: dict[DisputeStatus, frozenset[DisputeStatus]] = {
    DisputeStatus.OPENED: frozenset({DisputeStatus.IN_REVIEW, DisputeStatus.ESCALATED, DisputeStatus.REJECTED}),
    DisputeStatus.IN_REVIEW: frozenset({DisputeStatus.RESOLVED, DisputeStatus.REJECTED, DisputeStatus.ESCALATED}),
    DisputeStatus.ESCALATED: frozenset({DisputeStatus.IN_REVIEW, DisputeStatus.RESOLVED, DisputeStatus.REJECTED}),
    DisputeStatus.RESOLVED: frozenset(),
    DisputeStatus.REJECTED: frozenset(),
}

TERMINAL_STATUSES = frozenset(status for status, targets in ALLOWED_TRANSITIONS.items() if not targets)
OPEN_STATUSES = frozenset(DisputeStatus) - TERMINAL_STATUSES


class CaseStatusChange(DomainModel):
    from_status: DisputeStatus
    to_status: DisputeStatus
    at: UtcDatetime
    reason_code: Code


class DisputeCase(DomainModel):
    case_id: CaseId
    customer_id: CustomerId
    transaction_id: TransactionId
    product_id: ProductId
    reason: DisputeReason
    disputed_amount: Money
    status: DisputeStatus
    opened_at: UtcDatetime
    updated_at: UtcDatetime
    sla_due_at: UtcDatetime
    idempotency_key: IdempotencyKey
    origin_conversation_id: ConversationId | None = None
    status_history: tuple[CaseStatusChange, ...] = ()
    version: NonNegativeInt = 0

    @model_validator(mode="after")
    def _validate_times(self) -> Self:
        if self.updated_at < self.opened_at or self.sla_due_at < self.opened_at:
            raise ValueError("updated_at and sla_due_at cannot precede opened_at")
        return self

    @classmethod
    def open(
        cls,
        *,
        case_id: CaseId,
        transaction: Transaction,
        reason: DisputeReason,
        opened_at: datetime,
        sla_due_at: datetime,
        idempotency_key: IdempotencyKey,
        disputed_amount: Money | None = None,
        origin_conversation_id: ConversationId | None = None,
    ) -> Self:
        """Open a case for ``transaction``. Customer, product, and amount come from the transaction itself,
        so a case can never reference another customer's transaction."""
        amount = disputed_amount if disputed_amount is not None else transaction.amount
        if amount.currency is not transaction.amount.currency:
            raise ValueError("the disputed amount must be in the transaction currency")
        return cls(
            case_id=case_id,
            customer_id=transaction.customer_id,
            transaction_id=transaction.transaction_id,
            product_id=transaction.product_id,
            reason=reason,
            disputed_amount=amount,
            status=DisputeStatus.OPENED,
            opened_at=opened_at,
            updated_at=opened_at,
            sla_due_at=sla_due_at,
            idempotency_key=idempotency_key,
            origin_conversation_id=origin_conversation_id,
        )

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    def transition_to(self, status: DisputeStatus, *, at: datetime, reason_code: str) -> Self:
        """Move to ``status``, recording the change. Illegal moves raise ``InvalidCaseTransitionError``."""
        if status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidCaseTransitionError(f"a case cannot move from {self.status} to {status}")
        change = CaseStatusChange(from_status=self.status, to_status=status, at=at, reason_code=reason_code)
        if change.at < self.updated_at:
            raise InvalidCaseTransitionError("a status change cannot precede the last update")
        return self.evolve(status=status, updated_at=change.at, status_history=(*self.status_history, change))
