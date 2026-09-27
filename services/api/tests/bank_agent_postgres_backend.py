"""The contract-suite backend for the PostgreSQL adapters: the contract dataset loaded through the seeder."""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from bank_agent.adapters.persistence.postgres.audit import PostgresStandaloneAuditLog
from bank_agent.adapters.persistence.postgres.seed import PostgresSeeder, SeedBundle
from bank_agent.adapters.persistence.postgres.sessions import PostgresSessionStore
from bank_agent.adapters.persistence.postgres.unit_of_work import PostgresUnitOfWorkFactory
from bank_agent.domain.access import AccessContext
from bank_agent.ports.audit import AuditLog
from bank_agent.ports.sessions import SessionStore
from bank_agent.ports.unit_of_work import UnitOfWorkFactory
from bank_agent_contracts import ContractDataset, Readers
from bank_agent_postgres import app_engine, owner_engine, reset_database
from bank_agent_test_support import PostgresInstance


def bundle_of(data: ContractDataset) -> SeedBundle:
    return SeedBundle(
        customers=data.customers,
        products=data.products,
        transactions=data.transactions,
        complaints=data.complaints,
        credit_profiles=data.credit_profiles,
        cases=data.cases,
        credit_applications=data.credit_applications,
    )


class PostgresBackend:
    """PostgreSQL adapters over the session container, emptied before each test."""

    def __init__(self, instance: PostgresInstance) -> None:
        self._instance = instance
        self._engine = app_engine(instance)
        self._factory = PostgresUnitOfWorkFactory(self._engine)
        self._sessions = PostgresSessionStore(self._engine)

    async def seed(self, data: ContractDataset) -> None:
        await reset_database(self._instance)
        owner = owner_engine(self._instance)
        try:
            await PostgresSeeder(owner).load(bundle_of(data))
        finally:
            await owner.dispose()

    def readers(self, context: AccessContext) -> AbstractAsyncContextManager[Readers]:
        @asynccontextmanager
        async def _open() -> AsyncIterator[Readers]:
            async with self._factory(context) as uow:
                yield uow

        return _open()

    def uow_factory(self) -> UnitOfWorkFactory:
        return self._factory

    def session_store(self) -> SessionStore:
        return self._sessions

    def audit_log(self, context: AccessContext | None) -> AuditLog:
        return PostgresStandaloneAuditLog(self._engine, context)

    async def aclose(self) -> None:
        await self._engine.dispose()
