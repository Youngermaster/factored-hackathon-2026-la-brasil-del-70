"""The ladder decision: dependency signals and feature flags in, a ``DegradationStatus`` out. Pure and total.

Rules (the table in ``docs/operations/degradation.md``):

- No provider configured: the language model component is ``disabled`` and the level stays L0 (a configuration).
- Daily budget spent: L2 (``llm_budget_exhausted``), whatever the circuits say; a second provider would spend the
  same budget.
- Primary circuit open and a healthy fallback that the flag allows: L1 (``llm_primary_unavailable``).
- Primary open without a usable fallback: L2 (``llm_unavailable``). A half-open circuit is ``degraded``: its trial
  call decides, so it does not lower the level by itself.
- A learned model or the credit catalog failed to load at startup: L3 (``learned_models_unavailable``,
  ``credit_catalog_unavailable``).
- The database is unavailable or read-only: L4 (``database_unavailable``).

Template-only mode is on at L2 when its flag allows it; the stricter clarification budget is on at L2 and L3.
"""

from dataclasses import dataclass

from bank_agent.domain.degradation import Component, ComponentState, DegradationLevel, DegradationStatus

AVAILABLE = frozenset({ComponentState.OK, ComponentState.DEGRADED})


@dataclass(frozen=True)
class LadderFlags:
    """One feature flag per fallback (``DEGRADATION_*`` settings). L4 has none: failing closed is not optional."""

    fallback_provider: bool = True
    template_only: bool = True
    model_baselines: bool = True
    risk_band_fallback: bool = False


@dataclass(frozen=True)
class Signals:
    llm_primary: ComponentState = ComponentState.DISABLED
    llm_fallback: ComponentState = ComponentState.DISABLED
    budget_used_ratio: float = 0.0
    budget_exhausted: bool = False
    models_on_baseline: tuple[str, ...] = ()
    credit_catalog: ComponentState = ComponentState.OK
    database: ComponentState = ComponentState.DISABLED


def _llm(signals: Signals, flags: LadderFlags) -> tuple[DegradationLevel, str | None]:
    if signals.llm_primary is ComponentState.DISABLED:
        return DegradationLevel.NORMAL, None
    if signals.budget_exhausted:
        return DegradationLevel.TEMPLATE_ONLY, "llm_budget_exhausted"
    if signals.llm_primary is not ComponentState.UNAVAILABLE:
        return DegradationLevel.NORMAL, None
    if flags.fallback_provider and signals.llm_fallback in AVAILABLE:
        return DegradationLevel.FALLBACK_PROVIDER, "llm_primary_unavailable"
    return DegradationLevel.TEMPLATE_ONLY, "llm_unavailable"


def assess(signals: Signals, flags: LadderFlags) -> DegradationStatus:
    levels = [DegradationLevel.NORMAL]
    reasons: list[str] = []
    llm_level, llm_reason = _llm(signals, flags)
    levels.append(llm_level)
    if llm_reason is not None:
        reasons.append(llm_reason)
    if signals.models_on_baseline:
        levels.append(DegradationLevel.MODEL_BASELINES)
        reasons.append("learned_models_unavailable")
    if signals.credit_catalog is ComponentState.UNAVAILABLE:
        levels.append(DegradationLevel.MODEL_BASELINES)
        reasons.append("credit_catalog_unavailable")
    if signals.database is ComponentState.UNAVAILABLE:
        levels.append(DegradationLevel.DATABASE_UNAVAILABLE)
        reasons.append("database_unavailable")
    budget = ComponentState.DISABLED
    if signals.llm_primary is not ComponentState.DISABLED:
        budget = ComponentState.UNAVAILABLE if signals.budget_exhausted else ComponentState.OK
    components = {
        Component.LLM_PRIMARY: signals.llm_primary,
        Component.LLM_FALLBACK: signals.llm_fallback,
        Component.LLM_BUDGET: budget,
        Component.MODELS: ComponentState.DEGRADED if signals.models_on_baseline else ComponentState.OK,
        Component.CREDIT_CATALOG: signals.credit_catalog,
        Component.DATABASE: signals.database,
    }
    template_level = llm_level is DegradationLevel.TEMPLATE_ONLY
    baselines = DegradationLevel.MODEL_BASELINES in levels
    return DegradationStatus(
        level=max(levels),
        reasons=tuple(reasons),
        components=components,
        template_only=template_level and flags.template_only,
        stricter_clarification=template_level or baselines,
        budget_used_ratio=max(0.0, signals.budget_used_ratio),
    )


class StaticDegradation:
    """Implements ``DegradationSource`` with a fixed status: tests, CLIs, and the evaluation harness (L0 by default)."""

    def __init__(self, status: DegradationStatus | None = None) -> None:
        self.status = status or DegradationStatus()
        self.database_probes: list[bool] = []

    def current(self) -> DegradationStatus:
        return self.status

    def record_database(self, available: bool) -> None:
        self.database_probes.append(available)
