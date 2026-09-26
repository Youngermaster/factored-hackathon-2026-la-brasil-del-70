"""In-memory unit of work: staged writes, atomic commit, optimistic conflict detection."""

from types import TracebackType
from typing import Protocol, Self

from bank_agent.adapters.persistence.memory.repositories import (
    InMemoryAuditLog,
    InMemoryCaseRepository,
    InMemoryConversationRepository,
    InMemoryCustomerRepository,
    InMemoryExecutionRecordRepository,
    InMemoryHandoffRepository,
    InMemoryHistoricalComplaintRepository,
    InMemoryProductRepository,
    InMemoryTransactionRepository,
)
from bank_agent.adapters.persistence.memory.store import DirectView, InMemoryStore, TableView
from bank_agent.domain.access import AccessContext
from bank_agent.domain.errors import ConcurrencyConflictError


class Transactional(Protocol):
    def has_conflict(self) -> bool: ...

    def apply(self) -> None: ...

    def discard(self) -> None: ...


class InMemoryUnitOfWork:
    """Implements ``UnitOfWork``. Writes are staged per table and applied together on ``commit``.

    ``commit`` raises ``ConcurrencyConflictError`` and applies nothing when another unit of work committed a
    change to a key this one also wrote.
    """

    def __init__(self, store: InMemoryStore, context: AccessContext) -> None:
        self._context = context
        self._customers = TableView(store.customers)
        self._products = TableView(store.products)
        self._transactions = TableView(store.transactions)
        self._complaints = TableView(store.complaints)
        self._cases = TableView(store.cases)
        self._conversations = TableView(store.conversations)
        self._turns = TableView(store.turns)
        self._records = TableView(store.execution_records)
        self._handoffs = TableView(store.handoffs)
        self._audit_events = TableView(store.audit_events)
        self._views: tuple[Transactional, ...] = (
            self._customers,
            self._products,
            self._transactions,
            self._complaints,
            self._cases,
            self._conversations,
            self._turns,
            self._records,
            self._handoffs,
            self._audit_events,
        )

    @property
    def context(self) -> AccessContext:
        return self._context

    @property
    def customers(self) -> InMemoryCustomerRepository:
        return InMemoryCustomerRepository(self._customers, self._context)

    @property
    def products(self) -> InMemoryProductRepository:
        return InMemoryProductRepository(self._products, self._context)

    @property
    def transactions(self) -> InMemoryTransactionRepository:
        return InMemoryTransactionRepository(self._transactions, self._context)

    @property
    def cases(self) -> InMemoryCaseRepository:
        return InMemoryCaseRepository(self._cases, self._handoffs, self._context)

    @property
    def complaints(self) -> InMemoryHistoricalComplaintRepository:
        return InMemoryHistoricalComplaintRepository(self._complaints, self._context)

    @property
    def conversations(self) -> InMemoryConversationRepository:
        return InMemoryConversationRepository(self._conversations, self._turns, self._context)

    @property
    def execution_records(self) -> InMemoryExecutionRecordRepository:
        return InMemoryExecutionRecordRepository(self._records, self._context)

    @property
    def handoffs(self) -> InMemoryHandoffRepository:
        return InMemoryHandoffRepository(self._handoffs, self._context)

    @property
    def audit(self) -> InMemoryAuditLog:
        return InMemoryAuditLog(self._audit_events, self._context)

    async def commit(self) -> None:
        if any(view.has_conflict() for view in self._views):
            await self.rollback()
            raise ConcurrencyConflictError("another unit of work changed the same records")
        for view in self._views:
            view.apply()

    async def rollback(self) -> None:
        for view in self._views:
            view.discard()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await self.rollback()


class InMemoryUnitOfWorkFactory:
    """Implements ``UnitOfWorkFactory`` over one shared ``InMemoryStore``."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def __call__(self, context: AccessContext) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(self._store, context)


def standalone_audit_log(store: InMemoryStore, context: AccessContext | None = None) -> InMemoryAuditLog:
    """An audit log outside any unit of work: each append is committed immediately."""
    return InMemoryAuditLog(DirectView(store.audit_events), context)
