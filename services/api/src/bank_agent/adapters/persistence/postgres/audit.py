"""The standalone audit log: events outside a customer transaction (login, logout, step-up), each committed at once."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncEngine

from bank_agent.adapters.persistence.postgres.database import DatabaseRole, open_transaction, role_of
from bank_agent.adapters.persistence.postgres.repositories.records import PostgresAuditLog
from bank_agent.adapters.persistence.postgres.transaction import Tx
from bank_agent.domain.access import AccessContext, Role
from bank_agent.domain.audit import AuditEvent
from bank_agent.domain.errors import AccessContextError
from bank_agent.ports.audit import AuditQuery


class PostgresStandaloneAuditLog:
    """Implements ``AuditLog``. Without a context, events are written under the ``identity`` database role."""

    def __init__(self, engine: AsyncEngine, context: AccessContext | None = None) -> None:
        self._engine = engine
        self._context = context

    async def append(self, event: AuditEvent) -> None:
        context = self._context
        role = DatabaseRole.IDENTITY if context is None else role_of(context)
        customer = context.customer_id if context is not None and context.role is Role.CUSTOMER else None
        async with open_transaction(self._engine, role, customer) as connection:
            log = PostgresAuditLog(Tx(connection, context), customer_id=customer, list_context=context)
            await log.append(event)

    async def list(self, query: AuditQuery) -> Sequence[AuditEvent]:
        context = self._context
        if context is None or context.role is not Role.EVALUATOR:
            raise AccessContextError("listing audit events needs an evaluator context")
        async with open_transaction(self._engine, DatabaseRole.EVALUATOR) as connection:
            log = PostgresAuditLog(Tx(connection, context), customer_id=None, list_context=context)
            return await log.list(query)
