"""A circuit breaker around one provider stack.

Closed: calls pass; ``failure_threshold`` consecutive transient failures (timeout, rate limited, provider error
after retries) open the circuit. Open: calls fail at once with ``LlmCircuitOpenError`` until ``reset_after`` has
passed on the ``Clock``. Half-open: up to ``half_open_max_calls`` trial calls pass; a success closes the circuit
and a transient failure opens it again. Invalid output and provider rejections show the provider is reachable,
so they count as successes for the breaker.
"""

from datetime import datetime, timedelta
from enum import StrEnum

from bank_agent.adapters.llm.request import Generation, LlmDecorator, LlmRequest, Proceed
from bank_agent.domain.errors import LlmCircuitOpenError, LlmError
from bank_agent.ports.determinism import Clock
from bank_agent.ports.llm import LLMClient


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerDecorator(LlmDecorator):
    """Stops calling a failing provider for a while, then probes it."""

    def __init__(
        self,
        inner: LLMClient,
        *,
        clock: Clock,
        failure_threshold: int = 5,
        reset_after: timedelta = timedelta(seconds=30),
        half_open_max_calls: int = 1,
    ) -> None:
        if failure_threshold < 1 or half_open_max_calls < 1 or reset_after <= timedelta(0):
            raise ValueError("thresholds must be positive")
        super().__init__(inner)
        self.failure_threshold = failure_threshold
        self.reset_after = reset_after
        self.half_open_max_calls = half_open_max_calls
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: datetime | None = None
        self._trials_in_flight = 0

    @property
    def state(self) -> CircuitState:
        if (
            self._state is CircuitState.OPEN
            and self._opened_at is not None
            and self._clock.now() - self._opened_at >= self.reset_after
        ):
            self._state = CircuitState.HALF_OPEN
            self._trials_in_flight = 0
        return self._state

    def _open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._clock.now()
        self._failures = 0

    def _succeeded(self) -> None:
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = None

    def _failed(self, was_trial: bool) -> None:
        if was_trial:
            self._open()
            return
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._open()

    async def around(self, request: LlmRequest, proceed: Proceed) -> Generation:
        state = self.state
        if state is CircuitState.OPEN:
            raise LlmCircuitOpenError("the provider circuit is open")
        trial = state is CircuitState.HALF_OPEN
        if trial:
            if self._trials_in_flight >= self.half_open_max_calls:
                raise LlmCircuitOpenError("the provider circuit is half-open and a trial call is running")
            self._trials_in_flight += 1
        try:
            result = await proceed(request)
        except LlmError as error:
            if error.retryable:
                self._failed(trial)
            else:
                self._succeeded()
            raise
        finally:
            if trial:
                self._trials_in_flight = max(0, self._trials_in_flight - 1)
        self._succeeded()
        return result
