"""What every tool call shares: one unit of work under the session's context, and one audit event.

The audit event is appended in the same unit of work as the call's writes, so a committed write always has its
audit event and a rolled-back one never does. A call that fails with a domain error still records a failure
event. ``commit=False`` exists only for the test and evaluation failure injector (partial writes).
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from bank_agent.application.tools.auditing import record_call
from bank_agent.application.tools.context import SessionContext, ToolSettings
from bank_agent.domain.actions import ToolName
from bank_agent.domain.audit import AuditOutcome
from bank_agent.domain.errors import AuthorizationError, DomainError
from bank_agent.domain.identifiers import SourceRef
from bank_agent.ports.credit_catalog import CreditProductCatalog
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory


@dataclass(frozen=True)
class ToolDependencies:
    uow_factory: UnitOfWorkFactory
    catalog: CreditProductCatalog
    clock: Clock
    ids: IdGenerator
    settings: ToolSettings


class ToolCalls:
    def __init__(self, deps: ToolDependencies, context: SessionContext, *, commit: bool = True) -> None:
        self._deps = deps
        self._context = context
        self._commit = commit

    @property
    def context(self) -> SessionContext:
        return self._context

    async def _run[T](
        self,
        tool: ToolName,
        work: Callable[[UnitOfWork], Awaitable[T]],
        *,
        arguments: Mapping[str, object] | None = None,
        target: Callable[[T], SourceRef | None] = lambda _: None,
    ) -> T:
        deps = self._deps
        async with deps.uow_factory(self._context.access) as uow:
            try:
                result = await work(uow)
            except DomainError as error:
                await uow.rollback()
                outcome = AuditOutcome.DENIED if isinstance(error, AuthorizationError) else AuditOutcome.FAILURE
                await record_call(uow.audit, deps.ids, self._context, tool, outcome, arguments=arguments)
                await uow.commit()
                raise
            success = AuditOutcome.SUCCESS
            await record_call(
                uow.audit, deps.ids, self._context, tool, success, target=target(result), arguments=arguments
            )
            if self._commit:
                await uow.commit()
            return result
