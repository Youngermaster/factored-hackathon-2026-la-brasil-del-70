"""Scheduled tool failures for evaluation cases (``tool_failure_plan``).

``ToolFailureStep`` fails the ``on_call``-th call of a tool, ``times`` times in a row, counted over the whole case.
``ScheduledFailureTools`` wraps ``BankingTools`` the way the application's ``ToolFailureInjector`` does (a
decorator of the session toolset); it refuses production like that injector, and a partial write runs on tools
that never commit, so the caller gets a plausible result while the read-back finds nothing.
"""

from __future__ import annotations

from typing import Any, cast

from bank_agent.application.engine.tools import CreditProfileSource
from bank_agent.application.tools.banking import BankingTools, SessionToolset
from bank_agent.application.tools.base import ToolDependencies
from bank_agent.application.tools.context import SessionContext
from bank_agent.domain.actions import ToolFailureMode, ToolName
from bank_agent.domain.errors import ConfigurationError, ToolPermanentError, ToolTimeoutError, ToolTransientError
from bank_evals.systems.schedule import FailureSchedule

_RAISED: dict[ToolFailureMode, type[Exception]] = {
    ToolFailureMode.TIMEOUT: ToolTimeoutError,
    ToolFailureMode.TRANSIENT_ERROR: ToolTransientError,
    ToolFailureMode.PERMANENT_ERROR: ToolPermanentError,
}
TOOL_NAMES = frozenset(tool.value for tool in ToolName)


class _ScheduledToolset:
    def __init__(self, inner: SessionToolset, uncommitted: SessionToolset, schedule: FailureSchedule) -> None:
        self._inner, self._uncommitted, self._schedule = inner, uncommitted, schedule

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._inner, name)
        if name not in TOOL_NAMES or not callable(target):
            return target

        async def call(*args: Any, **kwargs: Any) -> Any:
            mode = self._schedule.next_mode(name)
            if mode in _RAISED:
                raise _RAISED[mode](f"injected {mode.value} for {name}")
            chosen = self._uncommitted if mode is ToolFailureMode.PARTIAL_WRITE else self._inner
            return await getattr(chosen, name)(*args, **kwargs)

        return call


class ScheduledFailureTools:
    """Implements the engine's ``ToolProvider`` over ``BankingTools`` with a failure schedule."""

    def __init__(self, tools: BankingTools, schedule: FailureSchedule, *, environment: str) -> None:
        if environment == "production":
            raise ConfigurationError("scheduled tool failures are refused in production")
        self._tools, self._schedule = tools, schedule

    def for_session(self, context: SessionContext) -> SessionToolset:
        wrapped = _ScheduledToolset(
            self._tools.for_session(context), self._tools.for_session(context, commit=False), self._schedule
        )
        return cast(SessionToolset, wrapped)

    def engine_only(self, context: SessionContext) -> CreditProfileSource:
        return self._tools.engine_only(context)

    @property
    def dependencies(self) -> ToolDependencies:
        return self._tools.dependencies
