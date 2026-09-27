from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from bank_agent.adapters.llm.budget import BudgetGuardDecorator, BudgetLimits, InMemoryBudgetLedger
from bank_agent.adapters.llm.cost import COST_METRIC, CostAccountingDecorator
from bank_agent.adapters.llm.prices import (
    ModelPrice,
    PriceBasis,
    PriceTable,
    PriceTableFile,
)
from bank_agent.domain.errors import (
    ConfigurationError,
    LlmBudgetExceededError,
    LlmInvalidOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from bank_agent.domain.identifiers import ConversationId, LineageId
from bank_agent.domain.intelligence import LlmCallContext, TokenUsage
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_llm import StubClient, call_structured, call_text

REPOSITORY_PRICES = Path(__file__).resolve().parents[4] / "config" / "llm_prices.yaml"
NOW = datetime(2026, 9, 26, 23, 59, tzinfo=UTC)


def _entry(model_id: str, inp: str, out: str, *, verified: bool) -> ModelPrice:
    return ModelPrice(
        model_id=model_id,
        input_usd_per_million=Decimal(inp),
        output_usd_per_million=Decimal(out),
        effective_date=date(2026, 9, 1),
        source_url="https://example.com/pricing",
        verified=verified,
    )


PRICES = PriceTable(
    PriceTableFile(
        schema_version=1,
        currency="USD",
        unverified_price_multiplier=Decimal(2),
        models=(
            _entry("verified/model", "1.00", "4.00", verified=True),
            _entry("unverified/model", "3.00", "10.00", verified=False),
        ),
    )
)


# --- Price table and cost math -------------------------------------------------------------------------------


def test_verified_prices_are_used_as_written() -> None:
    cost = PRICES.cost("verified/model", TokenUsage(input_tokens=1_000_000, output_tokens=500_000))

    assert cost == Decimal("3.00000000")
    assert PRICES.effective("verified/model").basis is PriceBasis.VERIFIED


def test_unverified_prices_are_multiplied() -> None:
    price = PRICES.effective("unverified/model")

    assert (price.input_usd_per_million, price.output_usd_per_million) == (Decimal(6), Decimal(20))
    assert price.basis is PriceBasis.UNVERIFIED
    assert PRICES.cost("unverified/model", TokenUsage(input_tokens=1000, output_tokens=100)) == Decimal("0.00800000")


def test_unknown_models_are_charged_at_the_highest_prices_times_the_multiplier() -> None:
    price = PRICES.effective("someone/else")

    assert (price.input_usd_per_million, price.output_usd_per_million) == (Decimal(6), Decimal(20))
    assert price.basis is PriceBasis.UNKNOWN_MODEL


def test_costs_round_up_to_eight_places() -> None:
    assert PRICES.cost("verified/model", TokenUsage(input_tokens=1, output_tokens=0)) == Decimal("0.00000100")
    assert PRICES.cost("verified/model", TokenUsage(input_tokens=0, output_tokens=0)) == Decimal("0E-8")
    tiny = PriceTable(
        PriceTableFile(
            schema_version=1,
            currency="USD",
            unverified_price_multiplier=Decimal(1),
            models=(_entry("t/m", "0.001", "0", verified=True),),
        )
    )
    assert tiny.cost("t/m", TokenUsage(input_tokens=1, output_tokens=0)) == Decimal("0.00000001")


def test_worst_output_cost_takes_the_most_expensive_configured_model() -> None:
    assert PRICES.worst_output_cost(("verified/model", "unverified/model"), 1000) == Decimal("0.02000000")
    assert PRICES.worst_output_cost(("verified/model",), 1000) == Decimal("0.00400000")
    assert PRICES.worst_output_cost((), 1000) == Decimal("0.02000000")


def test_the_repository_price_table_loads_and_every_hosted_entry_awaits_human_verification() -> None:
    table = PriceTable.from_yaml(REPOSITORY_PRICES)

    ids = {entry.model_id for entry in table.entries}
    assert {"anthropic/claude-sonnet-5", "anthropic/claude-haiku-4-5-20251001"} <= ids
    assert any(entry.model_id.startswith("openai/") for entry in table.entries)
    for entry in table.entries:
        assert entry.source_url.startswith("https://")
        if entry.model_id.startswith("ollama/"):
            continue
        assert not entry.verified
        assert table.effective(entry.model_id).basis is PriceBasis.UNVERIFIED


def test_the_local_ollama_model_is_verified_at_zero_cost_and_labeled_local() -> None:
    table = PriceTable.from_yaml(REPOSITORY_PRICES)

    (local,) = [entry for entry in table.entries if entry.model_id.startswith("ollama/")]
    assert (local.model_id, local.verified) == ("ollama/qwen2.5:7b-instruct", True)
    assert local.input_usd_per_million == local.output_usd_per_million == 0
    assert "Local development model" in local.notes
    effective = table.effective(local.model_id)
    assert (effective.basis, effective.input_usd_per_million) == (PriceBasis.VERIFIED, 0)


@pytest.mark.parametrize(
    "text",
    [
        "not: [valid",
        "schema_version: 1\ncurrency: USD\nunverified_price_multiplier: '0.5'\nmodels: []\n",
        "schema_version: 1\ncurrency: USD\nunverified_price_multiplier: '1'\nmodels:\n"
        "  - {model_id: a/b, input_usd_per_million: 1.5, output_usd_per_million: '1', effective_date: 2026-01-01,"
        " source_url: 'https://x.test', verified: true}\n",
    ],
)
def test_refuses_invalid_price_tables(tmp_path: Path, text: str) -> None:
    path = tmp_path / "prices.yaml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="missing or invalid"):
        PriceTable.from_yaml(path)


def test_refuses_duplicate_model_ids() -> None:
    with pytest.raises(ValueError, match="only once"):
        PriceTableFile(
            schema_version=1,
            currency="USD",
            unverified_price_multiplier=Decimal(1),
            models=(_entry("a/b", "1", "1", verified=True), _entry("a/b", "2", "2", verified=True)),
        )


def test_a_missing_price_table_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        PriceTable.from_yaml(tmp_path / "absent.yaml")


# --- Cost accounting decorator -------------------------------------------------------------------------------


async def test_cost_accounting_sets_the_cost_and_emits_a_metric() -> None:
    telemetry = RecordingTelemetry()
    stub = StubClient(model_id="verified/model", usage=TokenUsage(input_tokens=2000, output_tokens=1000))
    client = CostAccountingDecorator(stub, prices=PRICES, telemetry=telemetry)

    structured = await call_structured(client)
    text = await call_text(client)

    assert structured.cost_usd == Decimal("0.00600000")
    assert structured.value.answer == "yes"
    assert text.cost_usd == Decimal("0.00600000")
    values = telemetry.histograms[COST_METRIC].values
    assert values[0] == (0.006, {"gen_ai.response.model": "verified/model", "bank.llm.price_basis": "verified"})


# --- Budget guard --------------------------------------------------------------------------------------------

LIMITS = BudgetLimits(
    session_token_limit=5000, conversation_cost_limit_usd=Decimal("0.05"), daily_cost_limit_usd=Decimal("0.10")
)
CONTEXT = LlmCallContext(lineage_id=LineageId("lin-1"), conversation_id=ConversationId("conv-1"))


def _guard(stub: StubClient, clock: FixedClock, limits: BudgetLimits = LIMITS) -> BudgetGuardDecorator:
    return BudgetGuardDecorator(stub, limits=limits, prices=PRICES, model_ids=("verified/model",), clock=clock)


async def test_records_actual_tokens_and_cost_after_a_successful_call() -> None:
    stub = StubClient(usage=TokenUsage(input_tokens=1000, output_tokens=200), cost_usd=Decimal("0.0100"))
    guard = _guard(stub, FixedClock(NOW))

    await call_structured(guard, context=CONTEXT, max_output_tokens=500)

    assert guard.ledger.session_tokens["lin-1"] == 1200
    assert guard.ledger.conversation_cost["conv-1"] == Decimal("0.0100")
    assert guard.ledger.daily_cost[NOW.date()] == Decimal("0.0100")


async def test_uses_the_price_table_when_the_result_has_no_cost() -> None:
    stub = StubClient(model_id="unverified/model", usage=TokenUsage(input_tokens=1000, output_tokens=100))
    guard = _guard(stub, FixedClock(NOW))

    await call_text(guard, context=CONTEXT, max_output_tokens=100)

    assert guard.ledger.daily_cost[NOW.date()] == Decimal("0.00800000")


async def test_session_token_cap_counts_the_reservation() -> None:
    stub = StubClient(usage=TokenUsage(input_tokens=3000, output_tokens=1000), cost_usd=Decimal(0))
    guard = _guard(stub, FixedClock(NOW))
    await call_structured(guard, context=CONTEXT, max_output_tokens=500)

    with pytest.raises(LlmBudgetExceededError, match="session token cap"):
        await call_structured(guard, context=CONTEXT, max_output_tokens=1001)

    await call_structured(guard, context=CONTEXT, max_output_tokens=1000)
    assert len(stub.calls) == 2


async def test_conversation_cost_cap() -> None:
    stub = StubClient(cost_usd=Decimal("0.049"))
    guard = _guard(stub, FixedClock(NOW))
    await call_structured(guard, context=CONTEXT, max_output_tokens=10)

    with pytest.raises(LlmBudgetExceededError, match="conversation cost cap"):
        await call_structured(guard, context=CONTEXT, max_output_tokens=1000)

    other = LlmCallContext(conversation_id=ConversationId("conv-2"))
    await call_structured(guard, context=other, max_output_tokens=1000)


async def test_daily_cost_cap_resets_on_the_next_utc_day() -> None:
    clock = FixedClock(NOW)
    stub = StubClient(cost_usd=Decimal("0.099"))
    guard = _guard(stub, clock)
    await call_structured(guard, max_output_tokens=10)

    with pytest.raises(LlmBudgetExceededError, match="daily cost cap"):
        await call_structured(guard, max_output_tokens=1000)

    clock.advance(timedelta(minutes=1))
    await call_structured(guard, max_output_tokens=1000)
    assert guard.ledger.daily_cost[date(2026, 9, 27)] == Decimal("0.099")


async def test_a_zero_daily_budget_refuses_every_call() -> None:
    limits = BudgetLimits(
        session_token_limit=10, conversation_cost_limit_usd=Decimal(1), daily_cost_limit_usd=Decimal(0)
    )
    stub = StubClient()

    with pytest.raises(LlmBudgetExceededError):
        await call_text(_guard(stub, FixedClock(NOW), limits), max_output_tokens=1)

    assert stub.calls == []


@pytest.mark.parametrize("error", [LlmInvalidOutputError(), LlmTimeoutError()])
async def test_keeps_the_reservation_when_the_provider_may_have_billed(error: Exception) -> None:
    stub = StubClient(outcomes=[error])  # type: ignore[list-item]
    guard = _guard(stub, FixedClock(NOW))

    with pytest.raises(type(error)):
        await call_structured(guard, context=CONTEXT, max_output_tokens=1000)

    assert guard.ledger.session_tokens["lin-1"] == 1000
    assert guard.ledger.conversation_cost["conv-1"] == Decimal("0.00400000")


async def test_releases_the_reservation_after_other_errors() -> None:
    stub = StubClient(outcomes=[LlmProviderError()])
    guard = _guard(stub, FixedClock(NOW))

    with pytest.raises(LlmProviderError):
        await call_structured(guard, context=CONTEXT, max_output_tokens=1000)

    assert guard.ledger.session_tokens["lin-1"] == 0
    assert guard.ledger.daily_cost[NOW.date()] == 0


def test_budget_limits_are_validated() -> None:
    with pytest.raises(ValueError, match="positive"):
        BudgetLimits(session_token_limit=0, conversation_cost_limit_usd=Decimal(1), daily_cost_limit_usd=Decimal(1))


def test_the_ledger_ignores_missing_identifiers_except_for_the_day() -> None:
    ledger = InMemoryBudgetLedger()

    ledger.add(session=None, conversation=None, day=NOW.date(), tokens=10, cost=Decimal(1))

    assert dict(ledger.session_tokens) == {}
    assert dict(ledger.conversation_cost) == {}
    assert ledger.daily_cost[NOW.date()] == Decimal(1)
