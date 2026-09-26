"""Unit of work port: one transaction, bound to one access context, exposing every repository."""

from types import TracebackType
from typing import Protocol, Self

from bank_agent.domain.access import AccessContext
from bank_agent.ports.audit import AuditLog
from bank_agent.ports.repositories.cases import CaseRepository
from bank_agent.ports.repositories.complaints import HistoricalComplaintRepository
from bank_agent.ports.repositories.conversations import ConversationRepository
from bank_agent.ports.repositories.credit_applications import CreditApplicationRepository
from bank_agent.ports.repositories.credit_profiles import CreditProfileReader
from bank_agent.ports.repositories.customers import CustomerRepository
from bank_agent.ports.repositories.execution_records import ExecutionRecordRepository
from bank_agent.ports.repositories.handoffs import HandoffRepository
from bank_agent.ports.repositories.products import ProductRepository
from bank_agent.ports.repositories.transactions import TransactionRepository


class UnitOfWork(Protocol):
    """A transaction whose repositories are all bound to ``context``.

    Usage: ``async with factory(context) as uow: ...; await uow.commit()``.
    Preconditions: used once, inside ``async with``.
    Postconditions: writes become visible to other units of work only after ``commit``. Leaving the block
    without committing, or with an exception, rolls back. Reads inside the unit of work see its own writes.
    Errors: repository errors propagate unchanged; a failed commit raises and leaves nothing applied.
    Isolation: the PostgreSQL implementation (phase 05) sets ``app.customer_id`` and ``app.role`` from the
    context inside the transaction, so row-level security backs up the repositories' own scoping.
    """

    @property
    def context(self) -> AccessContext: ...

    @property
    def customers(self) -> CustomerRepository: ...

    @property
    def products(self) -> ProductRepository: ...

    @property
    def transactions(self) -> TransactionRepository: ...

    @property
    def cases(self) -> CaseRepository: ...

    @property
    def complaints(self) -> HistoricalComplaintRepository: ...

    @property
    def conversations(self) -> ConversationRepository: ...

    @property
    def execution_records(self) -> ExecutionRecordRepository: ...

    @property
    def handoffs(self) -> HandoffRepository: ...

    @property
    def audit(self) -> AuditLog: ...

    @property
    def credit_profiles(self) -> CreditProfileReader: ...

    @property
    def credit_applications(self) -> CreditApplicationRepository: ...

    async def commit(self) -> None:
        """Apply every write of this unit of work atomically."""
        ...

    async def rollback(self) -> None:
        """Discard every write of this unit of work."""
        ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None: ...


class UnitOfWorkFactory(Protocol):
    """Opens units of work. The only way application code reaches customer data.

    Preconditions: ``context`` comes from a verified session or a staff session, never from request data.
    Postconditions: each call returns a new, independent unit of work.
    Errors: none at creation; failures surface when the unit of work is used.
    Isolation: the context is fixed for the unit of work's lifetime and cannot be changed.
    """

    def __call__(self, context: AccessContext) -> UnitOfWork:
        """Return a new, not yet entered, unit of work bound to ``context``."""
        ...
