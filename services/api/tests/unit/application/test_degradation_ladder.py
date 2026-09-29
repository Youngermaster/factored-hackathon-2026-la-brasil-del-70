"""The degradation ladder decision table: every level, their combinations, and each feature flag."""

import pytest

from bank_agent.application.reliability.ladder import LadderFlags, Signals, StaticDegradation, assess
from bank_agent.domain.degradation import Component, ComponentState, DegradationLevel

OK, DEGRADED, DOWN, OFF = (
    ComponentState.OK,
    ComponentState.DEGRADED,
    ComponentState.UNAVAILABLE,
    ComponentState.DISABLED,
)
FLAGS = LadderFlags()


@pytest.mark.parametrize(
    ("signals", "level", "reasons", "template_only", "stricter"),
    [
        (Signals(), DegradationLevel.NORMAL, (), False, False),
        (Signals(llm_primary=OK, database=OK), DegradationLevel.NORMAL, (), False, False),
        (Signals(llm_primary=DEGRADED), DegradationLevel.NORMAL, (), False, False),
        (Signals(llm_primary=DOWN, llm_fallback=OK), DegradationLevel.FALLBACK_PROVIDER,
         ("llm_primary_unavailable",), False, False),
        (Signals(llm_primary=DOWN, llm_fallback=DEGRADED), DegradationLevel.FALLBACK_PROVIDER,
         ("llm_primary_unavailable",), False, False),
        (Signals(llm_primary=DOWN, llm_fallback=DOWN), DegradationLevel.TEMPLATE_ONLY,
         ("llm_unavailable",), True, True),
        (Signals(llm_primary=DOWN), DegradationLevel.TEMPLATE_ONLY, ("llm_unavailable",), True, True),
        (Signals(llm_primary=OK, budget_exhausted=True, budget_used_ratio=1.0), DegradationLevel.TEMPLATE_ONLY,
         ("llm_budget_exhausted",), True, True),
        (Signals(llm_primary=OK, budget_used_ratio=0.85), DegradationLevel.NORMAL, (), False, False),
        (Signals(models_on_baseline=("router",)), DegradationLevel.MODEL_BASELINES,
         ("learned_models_unavailable",), False, True),
        (Signals(credit_catalog=DOWN), DegradationLevel.MODEL_BASELINES, ("credit_catalog_unavailable",), False, True),
        (Signals(database=DOWN), DegradationLevel.DATABASE_UNAVAILABLE, ("database_unavailable",), False, False),
        (Signals(llm_primary=DOWN, models_on_baseline=("resolver",), database=DOWN),
         DegradationLevel.DATABASE_UNAVAILABLE,
         ("llm_unavailable", "learned_models_unavailable", "database_unavailable"), True, True),
    ],
)  # fmt: skip
def test_the_level_is_the_highest_active_condition(
    signals: Signals, level: DegradationLevel, reasons: tuple[str, ...], template_only: bool, stricter: bool
) -> None:
    status = assess(signals, FLAGS)
    assert (status.level, status.reasons, status.template_only, status.stricter_clarification) == (
        level,
        reasons,
        template_only,
        stricter,
    )


def test_an_unconfigured_model_is_a_configuration_not_a_degradation() -> None:
    status = assess(Signals(llm_primary=OFF, budget_exhausted=True), FLAGS)
    assert status.level is DegradationLevel.NORMAL
    assert status.components[Component.LLM_PRIMARY] is OFF
    assert status.components[Component.LLM_BUDGET] is OFF


def test_without_the_fallback_flag_a_primary_outage_is_template_only() -> None:
    status = assess(Signals(llm_primary=DOWN, llm_fallback=OK), LadderFlags(fallback_provider=False))
    assert (status.level, status.template_only) == (DegradationLevel.TEMPLATE_ONLY, True)


def test_without_the_template_only_flag_l2_still_reports_but_calls_are_attempted() -> None:
    status = assess(Signals(llm_primary=DOWN), LadderFlags(template_only=False))
    assert (status.level, status.template_only, status.stricter_clarification) == (
        DegradationLevel.TEMPLATE_ONLY,
        False,
        True,
    )


def test_components_and_labels_are_reported() -> None:
    status = assess(Signals(llm_primary=OK, budget_exhausted=True, models_on_baseline=("router",)), FLAGS)
    assert status.components[Component.LLM_BUDGET] is DOWN
    assert status.components[Component.MODELS] is DEGRADED
    assert status.level.label == "L3"
    assert status.degraded


def test_the_static_source_reports_its_status_and_records_probes() -> None:
    source = StaticDegradation()
    source.record_database(False)
    assert source.current().level is DegradationLevel.NORMAL
    assert source.database_probes == [False]
