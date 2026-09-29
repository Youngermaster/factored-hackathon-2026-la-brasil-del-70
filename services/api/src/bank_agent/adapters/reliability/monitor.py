"""``DegradationMonitor``: the live ``DegradationSource`` over the circuit breakers, the budget, and startup results.

It reads state the other adapters already keep (the breakers' state machines, the budget guard's last known daily
spend), the model and catalog load results the composition root recorded at startup, and the latest database probe.
Reading never blocks on I/O. Every call publishes the level, the component states, the circuit states, and the budget
ratio as gauges, and a change of level is logged once as ``degradation_level_changed``.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import structlog

from bank_agent.adapters.llm.budget import BudgetGuardDecorator
from bank_agent.adapters.llm.circuit_breaker import CircuitBreakerDecorator, CircuitState
from bank_agent.application.reliability.ladder import LadderFlags, Signals, assess
from bank_agent.domain.degradation import ComponentState, DegradationLevel, DegradationStatus
from bank_agent.ports.determinism import Clock
from bank_agent.ports.telemetry import Telemetry

_log = structlog.get_logger(__name__)
CIRCUIT_GAUGE: Final = {CircuitState.CLOSED: 0, CircuitState.HALF_OPEN: 1, CircuitState.OPEN: 2}
COMPONENT_GAUGE: Final = {
    ComponentState.OK: 0,
    ComponentState.DEGRADED: 1,
    ComponentState.UNAVAILABLE: 2,
    ComponentState.DISABLED: 3,
}
_CIRCUIT_COMPONENT: Final = {
    CircuitState.CLOSED: ComponentState.OK,
    CircuitState.HALF_OPEN: ComponentState.DEGRADED,
    CircuitState.OPEN: ComponentState.UNAVAILABLE,
}


class DatabaseHealth:
    """The latest database availability, told by the unit of work on every transaction and by readiness probes.

    Shared by the persistence adapters (which report) and the monitor (which reads); each failure also increments
    ``bank.database.unavailable``.
    """

    def __init__(self, telemetry: Telemetry | None = None) -> None:
        self.available = True
        self._failures = telemetry.counter("bank.database.unavailable") if telemetry is not None else None

    def record(self, available: bool) -> None:
        self.available = available
        if not available and self._failures is not None:
            self._failures.add(1)


@dataclass(frozen=True)
class LlmHealth:
    """The breakers and the budget guard of the gateway the composition root built (``None`` when absent)."""

    primary: CircuitBreakerDecorator | None = None
    fallback: CircuitBreakerDecorator | None = None
    budget: BudgetGuardDecorator | None = None
    primary_model: str = ""
    fallback_model: str = ""


class DegradationMonitor:
    """Implements ``DegradationSource``."""

    def __init__(
        self,
        *,
        clock: Clock,
        telemetry: Telemetry,
        flags: LadderFlags,
        llm: LlmHealth | None = None,
        models_on_baseline: Sequence[str] = (),
        credit_catalog: ComponentState = ComponentState.OK,
        database: DatabaseHealth | None = None,
    ) -> None:
        self._clock = clock
        self._flags = flags
        self._llm = llm or LlmHealth()
        self._models_on_baseline = models_on_baseline
        self._credit_catalog = credit_catalog
        self._database = database
        self._last_level: DegradationLevel | None = None
        self._level = telemetry.gauge("bank.degradation.level")
        self._components = telemetry.gauge("bank.degradation.component")
        self._circuits = telemetry.gauge("bank.llm.circuit.state")
        self._budget_ratio = telemetry.gauge("bank.llm.budget.daily_used_ratio")

    @property
    def flags(self) -> LadderFlags:
        return self._flags

    def record_database(self, available: bool) -> None:
        if self._database is not None:
            self._database.record(available)

    def _database_state(self) -> ComponentState:
        if self._database is None:
            return ComponentState.DISABLED
        return ComponentState.OK if self._database.available else ComponentState.UNAVAILABLE

    def _circuit(self, breaker: CircuitBreakerDecorator | None) -> ComponentState:
        return ComponentState.DISABLED if breaker is None else _CIRCUIT_COMPONENT[breaker.state]

    def signals(self) -> Signals:
        today = self._clock.now().date()
        budget = self._llm.budget
        return Signals(
            llm_primary=self._circuit(self._llm.primary),
            llm_fallback=self._circuit(self._llm.fallback),
            budget_used_ratio=budget.daily_used_ratio(today) if budget is not None else 0.0,
            budget_exhausted=budget.daily_exhausted(today) if budget is not None else False,
            models_on_baseline=tuple(self._models_on_baseline),
            credit_catalog=self._credit_catalog,
            database=self._database_state(),
        )

    def current(self) -> DegradationStatus:
        status = assess(self.signals(), self._flags)
        self._publish(status)
        if status.level is not self._last_level:
            if self._last_level is not None:
                _log.warning(
                    "degradation_level_changed",
                    level_from=self._last_level.label,
                    level_to=status.level.label,
                    reasons=list(status.reasons),
                )
            self._last_level = status.level
        return status

    def _publish(self, status: DegradationStatus) -> None:
        self._level.set(status.level.value)
        for component, state in status.components.items():
            self._components.set(COMPONENT_GAUGE[state], {"bank.component": component.value})
        for breaker, model in (
            (self._llm.primary, self._llm.primary_model),
            (self._llm.fallback, self._llm.fallback_model),
        ):
            if breaker is not None:
                self._circuits.set(CIRCUIT_GAUGE[breaker.state], {"bank.llm.model": model})
        if self._llm.budget is not None:
            self._budget_ratio.set(status.budget_used_ratio)
