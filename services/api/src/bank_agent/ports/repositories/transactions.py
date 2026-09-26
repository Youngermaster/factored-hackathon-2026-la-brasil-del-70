"""Transaction repository port."""

from collections.abc import Sequence
from typing import Annotated, Protocol, Self

from pydantic import Field, model_validator

from bank_agent.domain.base import DomainModel, UtcDatetime
from bank_agent.domain.identifiers import ProductId, TransactionId
from bank_agent.domain.money import Amount
from bank_agent.domain.transaction import Transaction, TransactionStatus

MAX_TRANSACTION_PAGE = 200


class TransactionQuery(DomainModel):
    """Filters for listing the bound customer's transactions. Every filter is optional except the limit.

    The amount bounds compare the amount in its own currency.
    """

    occurred_from: UtcDatetime | None = None
    occurred_to: UtcDatetime | None = None
    product_ids: tuple[ProductId, ...] = ()
    statuses: tuple[TransactionStatus, ...] = ()
    min_amount: Amount | None = None
    max_amount: Amount | None = None
    limit: Annotated[int, Field(ge=1, le=MAX_TRANSACTION_PAGE)] = 50

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.occurred_from and self.occurred_to and self.occurred_to < self.occurred_from:
            raise ValueError("occurred_to cannot precede occurred_from")
        if self.min_amount is not None and self.max_amount is not None and self.max_amount < self.min_amount:
            raise ValueError("max_amount cannot be below min_amount")
        return self


class TransactionReader(Protocol):
    """Reads the bound customer's transactions. Transactions are never written by the service.

    Preconditions: bound to a customer ``AccessContext``.
    Postconditions: ``list`` returns at most ``query.limit`` transactions, newest first, ties broken by
    ``transaction_id``; the time window is inclusive at both ends.
    Errors: ``AccessContextError`` for a staff context.
    Isolation: another customer's transaction id returns ``None``, exactly like an unknown id.
    """

    async def get(self, transaction_id: TransactionId) -> Transaction | None:
        """Return the transaction, or ``None`` when it is unknown or belongs to another customer."""
        ...

    async def list(self, query: TransactionQuery) -> Sequence[Transaction]:
        """Return the customer's transactions that match every filter in ``query``."""
        ...


class TransactionRepository(TransactionReader, Protocol):
    """The full transaction port. It adds no writes: transactions come from the core banking data."""
