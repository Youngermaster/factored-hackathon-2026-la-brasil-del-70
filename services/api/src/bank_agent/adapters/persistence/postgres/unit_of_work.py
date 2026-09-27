"""PostgreSQL unit of work: one transaction with the row-level security context set from an ``AccessContext``."""

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from bank_agent.adapters.persistence.postgres.database import DatabaseRole, role_of, set_context
from bank_agent.adapters.persistence.postgres.repositories.accounts import (
    PostgresCreditProfileReader,
    PostgresCustomerRepository,
    PostgresHistoricalComplaintRepository,
    PostgresProductRepository,
    PostgresTransactionRepository,
)
from bank_agent.adapters.persistence.postgres.repositories.cases import PostgresCaseRepository
from bank_agent.adapters.persistence.postgres.repositories.conversations import PostgresConversationRepository
from bank_agent.adapters.persistence.postgres.repositories.credit_applications import (
    PostgresCreditApplicationRepository,
)
from bank_agent.adapters.persistence.postgres.repositories.handoffs import PostgresHandoffRepository
from bank_agent.adapters.persistence.postgres.repositories.records import (
    PostgresAuditLog,
    PostgresExecutionRecordRepository,
)
from bank_agent.adapters.persistence.postgres.transaction import Tx
from bank_agent.domain.access import AccessContext, Role
from bank_agent.domain.errors import ConcurrencyConflictError


class PostgresUnitOfWork:
    """Implements ``UnitOfWork``. Entering opens a connection and a transaction and sets the context first.

    ``commit`` raises ``ConcurrencyConflictError`` and applies nothing when a write met a row that another open
    unit of work had locked (see ``Tx.lock_or_mark_conflicted``).
    """

    def __init__(self, engine: AsyncEngine, context: AccessContext) -> None:
        self._engine = engine
        self._context = context
        self._connection: AsyncConnection | None = None
        self._transaction: AsyncTransaction | None = None
        self._tx: Tx | None = None

    @property
    def context(self) -> AccessContext:
        return self._context

    def _open(self) -> Tx:
        if self._tx is None:
            raise RuntimeError("use the unit of work inside 'async with'")
        return self._tx

    @property
    def customers(self) -> PostgresCustomerRepository:
        return PostgresCustomerRepository(self._open())

    @property
    def products(self) -> PostgresProductRepository:
        return PostgresProductRepository(self._open())

    @property
    def transactions(self) -> PostgresTransactionRepository:
        return PostgresTransactionRepository(self._open())

    @property
    def cases(self) -> PostgresCaseRepository:
        return PostgresCaseRepository(self._open())

    @property
    def complaints(self) -> PostgresHistoricalComplaintRepository:
        return PostgresHistoricalComplaintRepository(self._open())

    @property
    def conversations(self) -> PostgresConversationRepository:
        return PostgresConversationRepository(self._open())

    @property
    def execution_records(self) -> PostgresExecutionRecordRepository:
        return PostgresExecutionRecordRepository(self._open())

    @property
    def handoffs(self) -> PostgresHandoffRepository:
        return PostgresHandoffRepository(self._open())

    @property
    def audit(self) -> PostgresAuditLog:
        customer = self._context.customer_id if self._context.role is Role.CUSTOMER else None
        return PostgresAuditLog(self._open(), customer_id=customer, list_context=self._context)

    @property
    def credit_profiles(self) -> PostgresCreditProfileReader:
        return PostgresCreditProfileReader(self._open())

    @property
    def credit_applications(self) -> PostgresCreditApplicationRepository:
        return PostgresCreditApplicationRepository(self._open())

    async def _restart(self) -> None:
        """Begin a new transaction with the same context, so later reads never run without one."""
        if self._connection is not None and self._tx is not None:
            self._transaction = await self._connection.begin()
            await set_context(self._connection, role_of(self._context), self._context.customer_id)
            self._tx.conflicted = False

    async def commit(self) -> None:
        tx = self._open()
        if self._transaction is None or not self._transaction.is_active:
            raise RuntimeError("the unit of work has no open transaction")
        if tx.conflicted:
            await self._transaction.rollback()
            await self._restart()
            raise ConcurrencyConflictError("another unit of work changed the same records")
        await self._transaction.commit()
        await self._restart()

    async def rollback(self) -> None:
        if self._transaction is not None and self._transaction.is_active:
            await self._transaction.rollback()
        await self._restart()

    async def __aenter__(self) -> Self:
        self._connection = await self._engine.connect()
        self._transaction = await self._connection.begin()
        await set_context(self._connection, role_of(self._context), self._context.customer_id)
        self._tx = Tx(self._connection, self._context)
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        try:
            if self._transaction is not None and self._transaction.is_active:
                await self._transaction.rollback()
        finally:
            if self._connection is not None:
                await self._connection.close()
            self._connection = None
            self._transaction = None


class PostgresUnitOfWorkFactory:
    """Implements ``UnitOfWorkFactory`` over one application-role engine."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def __call__(self, context: AccessContext) -> PostgresUnitOfWork:
        return PostgresUnitOfWork(self._engine, context)


__all__ = ["DatabaseRole", "PostgresUnitOfWork", "PostgresUnitOfWorkFactory"]
