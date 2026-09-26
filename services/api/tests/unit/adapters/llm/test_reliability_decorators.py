"""Timeout, bounded retry, circuit breaker, and fallback, each on its own over a stub client."""

from datetime import UTC, datetime, timedelta

import pytest

from bank_agent.adapters.llm.circuit_breaker import CircuitBreakerDecorator, CircuitState
from bank_agent.adapters.llm.fallback import FallbackDecorator
from bank_agent.adapters.llm.retry import BoundedRetryDecorator
from bank_agent.adapters.llm.timeout import TimeoutDecorator
from bank_agent.domain.errors import (
    LlmBudgetExceededError,
    LlmCircuitOpenError,
    LlmError,
    LlmInvalidOutputError,
    LlmProviderError,
    LlmProviderRejectedError,
    LlmRateLimitedError,
    LlmTimeoutError,
)
from bank_agent.testing.clock import FixedClock
from bank_agent_llm import StubClient, call_structured, call_text

START = datetime(2026, 9, 26, 12, tzinfo=UTC)


class FakeSleeper:
    """Records requested delays and advances a fixed clock instead of sleeping."""

    def __init__(self, clock: FixedClock) -> None:
        self.clock = clock
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)
        self.clock.advance(timedelta(seconds=seconds))


# --- Timeout -------------------------------------------------------------------------------------------------


async def test_timeout_raises_a_typed_error_when_the_call_is_too_slow() -> None:
    client = TimeoutDecorator(StubClient(delay=0.5), seconds=0.01)

    with pytest.raises(LlmTimeoutError, match="no reply within"):
        await call_structured(client)


async def test_timeout_passes_fast_calls_through() -> None:
    stub = StubClient()

    result = await call_text(TimeoutDecorator(stub, seconds=5))

    assert result.text == "hola"
    assert len(stub.calls) == 1


def test_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        TimeoutDecorator(StubClient(), seconds=0)


# --- Bounded retry -------------------------------------------------------------------------------------------


def _retry(stub: StubClient, sleeper: FakeSleeper) -> BoundedRetryDecorator:
    return BoundedRetryDecorator(stub, base_delay_seconds=0.5, max_delay_seconds=4.0, sleep=sleeper, jitter=lambda: 1.0)


@pytest.mark.parametrize("error", [LlmTimeoutError(), LlmRateLimitedError(), LlmProviderError()])
async def test_retries_transient_errors_then_succeeds(error: LlmError) -> None:
    stub = StubClient(outcomes=[error, error, "ok"])
    sleeper = FakeSleeper(FixedClock(START))

    result = await call_structured(_retry(stub, sleeper))

    assert result.value.answer == "yes"
    assert len(stub.calls) == 3
    assert sleeper.delays == [0.5, 1.0]


async def test_gives_up_after_two_retries_with_the_last_error() -> None:
    stub = StubClient(outcomes=[LlmTimeoutError()])
    sleeper = FakeSleeper(FixedClock(START))

    with pytest.raises(LlmTimeoutError):
        await call_structured(_retry(stub, sleeper))

    assert len(stub.calls) == 3
    assert len(sleeper.delays) == 2
    assert sleeper.clock.now() - START < timedelta(seconds=2)


@pytest.mark.parametrize("error", [LlmInvalidOutputError(), LlmProviderRejectedError(), LlmBudgetExceededError()])
async def test_never_retries_non_transient_errors(error: LlmError) -> None:
    stub = StubClient(outcomes=[error])
    sleeper = FakeSleeper(FixedClock(START))

    with pytest.raises(type(error)):
        await call_structured(_retry(stub, sleeper))

    assert len(stub.calls) == 1
    assert sleeper.delays == []


def test_backoff_is_exponential_capped_and_jittered_between_half_and_full() -> None:
    low = BoundedRetryDecorator(StubClient(), base_delay_seconds=1, max_delay_seconds=3, jitter=lambda: 0.0)
    high = BoundedRetryDecorator(StubClient(), base_delay_seconds=1, max_delay_seconds=3, jitter=lambda: 0.999)

    assert [low.delay_for(n) for n in range(4)] == [0.5, 1.0, 1.5, 1.5]
    assert [round(high.delay_for(n), 3) for n in range(4)] == [1.0, 1.999, 2.998, 2.998]


def test_retry_bounds_are_validated() -> None:
    with pytest.raises(ValueError, match="between 0 and 2"):
        BoundedRetryDecorator(StubClient(), max_retries=3)
    with pytest.raises(ValueError, match="delays"):
        BoundedRetryDecorator(StubClient(), base_delay_seconds=2, max_delay_seconds=1)


async def test_zero_retries_calls_once() -> None:
    stub = StubClient(outcomes=[LlmProviderError()])

    with pytest.raises(LlmProviderError):
        await call_text(BoundedRetryDecorator(stub, max_retries=0))

    assert len(stub.calls) == 1


# --- Circuit breaker -----------------------------------------------------------------------------------------


def _state(breaker: CircuitBreakerDecorator) -> CircuitState:
    return breaker.state


def _breaker(stub: StubClient, clock: FixedClock) -> CircuitBreakerDecorator:
    return CircuitBreakerDecorator(
        stub, clock=clock, failure_threshold=2, reset_after=timedelta(seconds=30), half_open_max_calls=1
    )


async def test_opens_after_consecutive_transient_failures_and_fails_fast() -> None:
    stub = StubClient(outcomes=[LlmProviderError()])
    breaker = _breaker(stub, FixedClock(START))

    for _ in range(2):
        with pytest.raises(LlmProviderError):
            await call_structured(breaker)
    assert _state(breaker) is CircuitState.OPEN

    with pytest.raises(LlmCircuitOpenError):
        await call_structured(breaker)
    assert len(stub.calls) == 2


async def test_half_open_trial_success_closes_the_circuit() -> None:
    clock = FixedClock(START)
    stub = StubClient(outcomes=[LlmTimeoutError(), LlmTimeoutError(), "ok"])
    breaker = _breaker(stub, clock)
    for _ in range(2):
        with pytest.raises(LlmTimeoutError):
            await call_structured(breaker)

    clock.advance(timedelta(seconds=29))
    assert _state(breaker) is CircuitState.OPEN
    clock.advance(timedelta(seconds=1))
    assert _state(breaker) is CircuitState.HALF_OPEN

    await call_structured(breaker)
    assert _state(breaker) is CircuitState.CLOSED


async def test_half_open_trial_failure_opens_again() -> None:
    clock = FixedClock(START)
    stub = StubClient(outcomes=[LlmRateLimitedError()])
    breaker = _breaker(stub, clock)
    for _ in range(2):
        with pytest.raises(LlmRateLimitedError):
            await call_structured(breaker)
    clock.advance(timedelta(seconds=30))

    with pytest.raises(LlmRateLimitedError):
        await call_structured(breaker)

    assert _state(breaker) is CircuitState.OPEN
    with pytest.raises(LlmCircuitOpenError):
        await call_structured(breaker)


async def test_half_open_allows_only_the_configured_number_of_trials() -> None:
    clock = FixedClock(START)
    slow = StubClient(outcomes=[LlmProviderError(), LlmProviderError(), "ok"])
    breaker = _breaker(slow, clock)
    for _ in range(2):
        with pytest.raises(LlmProviderError):
            await call_structured(breaker)
    clock.advance(timedelta(seconds=30))
    assert _state(breaker) is CircuitState.HALF_OPEN
    breaker._trials_in_flight = 1  # a trial call is running

    with pytest.raises(LlmCircuitOpenError, match="trial call is running"):
        await call_structured(breaker)


async def test_invalid_output_and_rejections_do_not_count_as_failures() -> None:
    stub = StubClient(outcomes=[LlmProviderError(), LlmInvalidOutputError(), LlmProviderError(), "ok"])
    breaker = _breaker(stub, FixedClock(START))

    with pytest.raises(LlmProviderError):
        await call_structured(breaker)
    with pytest.raises(LlmInvalidOutputError):
        await call_structured(breaker)
    with pytest.raises(LlmProviderError):
        await call_structured(breaker)

    assert _state(breaker) is CircuitState.CLOSED


def test_breaker_thresholds_are_validated() -> None:
    with pytest.raises(ValueError, match="positive"):
        CircuitBreakerDecorator(StubClient(), clock=FixedClock(START), failure_threshold=0)


# --- Fallback ------------------------------------------------------------------------------------------------


async def test_uses_the_primary_when_it_succeeds() -> None:
    primary, fallback = StubClient(model_id="p/1"), StubClient(model_id="f/1")

    result = await call_structured(FallbackDecorator(primary, fallback))

    assert result.model_id == "p/1"
    assert fallback.calls == []


@pytest.mark.parametrize("error", [LlmTimeoutError(), LlmCircuitOpenError(), LlmInvalidOutputError()])
async def test_falls_back_when_the_primary_fails(error: LlmError) -> None:
    primary = StubClient(outcomes=[error], model_id="p/1")
    fallback = StubClient(model_id="f/1")

    result = await call_text(FallbackDecorator(primary, fallback))

    assert result.model_id == "f/1"
    assert len(primary.calls) == len(fallback.calls) == 1


async def test_raises_the_fallback_error_chained_to_the_primary_error() -> None:
    primary = StubClient(outcomes=[LlmTimeoutError()])
    fallback = StubClient(outcomes=[LlmRateLimitedError()])

    with pytest.raises(LlmRateLimitedError) as raised:
        await call_structured(FallbackDecorator(primary, fallback))

    assert isinstance(raised.value.__cause__, LlmTimeoutError)


async def test_budget_errors_never_reach_the_fallback() -> None:
    primary = StubClient(outcomes=[LlmBudgetExceededError()])
    fallback = StubClient()

    with pytest.raises(LlmBudgetExceededError):
        await call_structured(FallbackDecorator(primary, fallback))

    assert fallback.calls == []
