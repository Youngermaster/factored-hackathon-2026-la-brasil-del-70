"""PostgreSQL unit of work: one transaction with the row-level security context set from an ``AccessContext``."""

from types import TracebackType
from typing import Self

import structlog
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from bank_agent.adapters.persistence.postgres.database import (
    AvailabilityListener,
    DatabaseRole,
    is_unavailable,
    role_of,
    set_context,
    unavailable,
)
from bank_agent.adapters.persistence.postgres.repositories.accounts import (
    PostgresCreditProfileReader,
    PostgresCustomerRepository,
    PostgresHistoricalComplaintRepository,
    PostgresProductRepository,
    PostgresTransactionRepository,
)
from bank_agent.adapters.persistence.postgres.repositories.action_ledger import PostgresActionLedger
from bank_agent.adapters.persistence.postgres.repositories.assistant_profiles import PostgresAssistantProfileRepository
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

_log = structlog.get_logger(__name__)


class PostgresUnitOfWork:
    """Implements ``UnitOfWork``. Entering opens a connection and a transaction and sets the context first.

    ``commit`` raises ``ConcurrencyConflictError`` and applies nothing when a write met a row that another open
    unit of work had locked (see ``Tx.lock_or_mark_conflicted``).
    """

    def __init__(
        self, engine: AsyncEngine, context: AccessContext, listener: AvailabilityListener | None = None
    ) -> None:
        self._engine = engine
        self._context = context
        self._listener = listener
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
    def assistant_profiles(self) -> PostgresAssistantProfileRepository:
        return PostgresAssistantProfileRepository(self._open())

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

    @property
    def action_ledger(self) -> PostgresActionLedger:
        return PostgresActionLedger(self._open())

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

    def _record(self, available: bool) -> None:
        if self._listener is not None:
            self._listener.record(available)

    async def __aenter__(self) -> Self:
        try:
            self._connection = await self._engine.connect()
            self._transaction = await self._connection.begin()
            await set_context(self._connection, role_of(self._context), self._context.customer_id)
        except Exception as error:
            await self._close_quietly()
            if is_unavailable(error):
                self._record(False)
                raise unavailable(error) from error
            raise
        self._tx = Tx(self._connection, self._context)
        self._record(True)
        return self

    async def _close_quietly(self) -> None:
        """Release the connection after an availability failure; a second failure changes nothing."""
        try:
            if self._connection is not None:
                await self._connection.close()
        except Exception as error:  # the database is already known to be unavailable
            _log.debug("database_close_failed", error_type=type(error).__name__)
        self._connection = None
        self._transaction = None

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        if exc is not None and not isinstance(exc, Exception):
            # Cancelled (a tool timeout) or shutting down: release the connection and let the cancellation through.
            await self._close_quietly()
            return
        if exc is not None and is_unavailable(exc):
            self._record(False)
            await self._close_quietly()
            raise unavailable(exc) from exc
        try:
            if self._transaction is not None and self._transaction.is_active:
                await self._transaction.rollback()
        except Exception as error:
            if not is_unavailable(error):
                raise
            self._record(False)
            await self._close_quietly()
            raise unavailable(error) from error
        finally:
            if self._connection is not None:
                await self._connection.close()
            self._connection = None
            self._transaction = None


class PostgresUnitOfWorkFactory:
    """Implements ``UnitOfWorkFactory`` over one application-role engine."""

    def __init__(self, engine: AsyncEngine, listener: AvailabilityListener | None = None) -> None:
        self._engine = engine
        self._listener = listener

    def __call__(self, context: AccessContext) -> PostgresUnitOfWork:
        return PostgresUnitOfWork(self._engine, context, self._listener)


__all__ = ["DatabaseRole", "PostgresUnitOfWork", "PostgresUnitOfWorkFactory"]
