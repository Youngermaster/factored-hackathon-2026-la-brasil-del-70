"""The degradation monitor over real breakers and a real budget guard: levels, gauges, alerts, and recovery."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
import structlog

from bank_agent.adapters.llm.budget import BudgetGuardDecorator, BudgetLimits
from bank_agent.adapters.llm.circuit_breaker import CircuitBreakerDecorator
from bank_agent.adapters.llm.prices import ModelPrice, PriceTable, PriceTableFile
from bank_agent.adapters.reliability.monitor import DegradationMonitor, LlmHealth
from bank_agent.application.reliability.ladder import LadderFlags
from bank_agent.domain.degradation import ComponentState, DegradationLevel
from bank_agent.domain.errors import LlmBudgetExceededError, LlmProviderError
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_llm import StubClient, call_text

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
PRICES = PriceTable(
    PriceTableFile(
        schema_version=1,
        currency="USD",
        unverified_price_multiplier=Decimal(2),
        models=(
            ModelPrice(
                model_id="stub/model",
                input_usd_per_million=Decimal("1.00"),
                output_usd_per_million=Decimal("4.00"),
                effective_date=date(2026, 9, 1),
                source_url="https://example.com/pricing",
                verified=True,
            ),
        ),
    )
)


def _breaker(stub: StubClient, clock: FixedClock) -> CircuitBreakerDecorator:
    return CircuitBreakerDecorator(stub, clock=clock, failure_threshold=2, reset_after=timedelta(seconds=30))


async def test_an_open_primary_with_a_fallback_is_l1_and_without_it_l2_then_recovers() -> None:
    clock, telemetry = FixedClock(NOW), RecordingTelemetry()
    primary = _breaker(StubClient(outcomes=[LlmProviderError()]), clock)
    fallback = _breaker(StubClient(), clock)
    health = LlmHealth(primary=primary, fallback=fallback, primary_model="p/1", fallback_model="f/1")
    monitor = DegradationMonitor(clock=clock, telemetry=telemetry, flags=LadderFlags(), llm=health)
    assert monitor.current().level is DegradationLevel.NORMAL
    for _ in range(2):
        with pytest.raises(LlmProviderError):
            await call_text(primary)
    assert monitor.current().level is DegradationLevel.FALLBACK_PROVIDER
    assert telemetry.gauges["bank.llm.circuit.state"].last(**{"bank.llm.model": "p/1"}) == 2

    alone = DegradationMonitor(clock=clock, telemetry=telemetry, flags=LadderFlags(), llm=LlmHealth(primary=primary))
    status = alone.current()
    assert (status.level, status.template_only) == (DegradationLevel.TEMPLATE_ONLY, True)
    assert telemetry.gauges["bank.degradation.level"].last() == 2

    clock.advance(timedelta(seconds=31))
    assert alone.current().level is DegradationLevel.NORMAL
    assert alone.current().components["llm_primary"] is ComponentState.DEGRADED  # type: ignore[index]


async def test_the_budget_alerts_at_80_percent_and_is_template_only_at_100() -> None:
    clock, telemetry = FixedClock(NOW), RecordingTelemetry()
    stub = StubClient(cost_usd=Decimal("0.085"))
    limits = BudgetLimits(
        session_token_limit=100_000, conversation_cost_limit_usd=Decimal(10), daily_cost_limit_usd=Decimal("0.10")
    )
    guard = BudgetGuardDecorator(
        stub, limits=limits, prices=PRICES, model_ids=("stub/model",), clock=clock, telemetry=telemetry
    )
    health = LlmHealth(primary=_breaker(StubClient(), clock), budget=guard)
    monitor = DegradationMonitor(clock=clock, telemetry=telemetry, flags=LadderFlags(), llm=health)
    with structlog.testing.capture_logs() as logs:
        await call_text(guard, max_output_tokens=10)
    assert [entry["event"] for entry in logs] == ["llm_budget_alert"]
    status = monitor.current()
    assert status.level is DegradationLevel.NORMAL
    assert status.budget_used_ratio == pytest.approx(0.85)
    assert telemetry.gauges["bank.llm.budget.daily_used_ratio"].last() == pytest.approx(0.85)

    with pytest.raises(LlmBudgetExceededError, match="daily cost cap"):
        await call_text(guard, max_output_tokens=10_000)
    status = monitor.current()
    assert (status.level, status.reasons, status.template_only) == (
        DegradationLevel.TEMPLATE_ONLY,
        ("llm_budget_exhausted",),
        True,
    )
    assert telemetry.counters["bank.llm.budget.refusals"].points == [(1, {"bank.llm.budget.cap": "daily_cost"})]

    clock.advance(timedelta(days=1))
    assert monitor.current().level is DegradationLevel.NORMAL


def test_startup_failures_and_database_probes_set_l3_and_l4_and_log_level_changes() -> None:
    clock, telemetry = FixedClock(NOW), RecordingTelemetry()
    served: list[str] = []
    monitor = DegradationMonitor(
        clock=clock,
        telemetry=telemetry,
        flags=LadderFlags(),
        models_on_baseline=served,
        credit_catalog=ComponentState.UNAVAILABLE,
        database_configured=True,
    )
    assert monitor.current().level is DegradationLevel.MODEL_BASELINES
    served.append("router")
    assert "learned_models_unavailable" in monitor.current().reasons
    with structlog.testing.capture_logs() as logs:
        monitor.record_database(False)
        assert monitor.current().level is DegradationLevel.DATABASE_UNAVAILABLE
        monitor.record_database(True)
        assert monitor.current().level is DegradationLevel.MODEL_BASELINES
    assert [(entry["level_from"], entry["level_to"]) for entry in logs] == [("L3", "L4"), ("L4", "L3")]
    assert telemetry.gauges["bank.degradation.component"].last(**{"bank.component": "database"}) == 0


def test_without_a_database_the_probe_changes_nothing() -> None:
    monitor = DegradationMonitor(clock=FixedClock(NOW), telemetry=RecordingTelemetry(), flags=LadderFlags())
    monitor.record_database(False)
    assert monitor.current().level is DegradationLevel.NORMAL
    assert monitor.flags == LadderFlags()
