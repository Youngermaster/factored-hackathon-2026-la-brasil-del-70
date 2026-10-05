"""The provider side of the embedding gateway: one batch call, and the decorators that wrap it.

Order, outermost first (built in ``bootstrap/embeddings.py``):

1. ``RedactingEmbedder`` (``gateway.py``, on the ``Embedder`` port): the query text is redacted before anything below.
2. ``GatewayEmbedder`` (``gateway.py``): batches, checks the vectors, and implements the port over a backend.
3. ``CostAccountingEmbedding``: prices each successful call from the price table and records it.
4. ``CircuitBreakingEmbedding``: stops calling a failing provider for a while, then probes it.
5. ``RetryingEmbedding``: bounded retry of transient failures with backoff and jitter.
6. The provider (``LiteLLMEmbedding``), whose call carries the timeout.

The same order as the language model gateway (``bootstrap/llm.py``), synchronous because retrieval runs in a worker
thread. There is no budget guard: a query embedding costs about 20 input tokens, so one million queries cost about
0.44 USD at the verified price (ADR 0047), and the API's rate limits already bound the call rate.
"""

import secrets
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Final, Protocol

from bank_agent.adapters.llm.cost import COST_METRIC
from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.domain.errors import EmbeddingCircuitOpenError, RetrievalBackendError
from bank_agent.domain.intelligence import TokenUsage
from bank_agent.domain.vectors import Vector
from bank_agent.ports.determinism import Clock
from bank_agent.ports.telemetry import Telemetry

MAX_RETRIES_ALLOWED: Final = 2
EMBEDDING_OPERATION: Final = "embeddings"
_SYSTEM_RANDOM: Final = secrets.SystemRandom()


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: tuple[Vector, ...]
    input_tokens: int
    model_id: str
    cost_usd: Decimal | None = None


class EmbeddingBackend(Protocol):
    """One provider call for a batch of texts. Errors: only the ``RetrievalBackendError`` family."""

    @property
    def model_id(self) -> str: ...

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch: ...


class EmbeddingDecorator:
    """Base for decorators that keep the backend's ``model_id``."""

    def __init__(self, inner: EmbeddingBackend) -> None:
        self.inner = inner

    @property
    def model_id(self) -> str:
        return self.inner.model_id


class RetryingEmbedding(EmbeddingDecorator):
    """Retries ``retryable`` errors at most ``max_retries`` times; the delay before retry ``n`` (0-based) is
    ``min(max_delay, base_delay * 2**n)`` scaled by a factor in ``[0.5, 1.0)``."""

    def __init__(
        self,
        inner: EmbeddingBackend,
        *,
        max_retries: int = 1,
        base_delay_seconds: float = 0.2,
        max_delay_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = _SYSTEM_RANDOM.random,
    ) -> None:
        if not 0 <= max_retries <= MAX_RETRIES_ALLOWED:
            raise ValueError(f"max_retries must be between 0 and {MAX_RETRIES_ALLOWED}")
        if base_delay_seconds < 0 or max_delay_seconds < base_delay_seconds:
            raise ValueError("delays must satisfy 0 <= base_delay <= max_delay")
        super().__init__(inner)
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self._sleep = sleep
        self._jitter = jitter

    def delay_for(self, retry: int) -> float:
        ceiling = min(self.max_delay_seconds, self.base_delay_seconds * 2.0**retry)
        return ceiling * (0.5 + self._jitter() / 2)

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        retry = 0
        while True:
            try:
                return self.inner.embed(texts)
            except RetrievalBackendError as error:
                if not error.retryable or retry >= self.max_retries:
                    raise
                self._sleep(self.delay_for(retry))
                retry += 1


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakingEmbedding(EmbeddingDecorator):
    """Closed: calls pass, and ``failure_threshold`` consecutive transient failures open the circuit. Open: calls fail
    at once with ``EmbeddingCircuitOpenError`` until ``reset_after`` has passed on the ``Clock``. Half-open: one trial
    call passes; a success closes the circuit and a transient failure opens it again. A rejection shows the provider
    is reachable, so it counts as a success. Thread-safe."""

    def __init__(
        self,
        inner: EmbeddingBackend,
        *,
        clock: Clock,
        failure_threshold: int = 5,
        reset_after: timedelta = timedelta(seconds=30),
    ) -> None:
        if failure_threshold < 1 or reset_after <= timedelta(0):
            raise ValueError("thresholds must be positive")
        super().__init__(inner)
        self.failure_threshold = failure_threshold
        self.reset_after = reset_after
        self._clock = clock
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: datetime | None = None
        self._trial_running = False

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._current()

    def _current(self) -> CircuitState:
        if (
            self._state is CircuitState.OPEN
            and self._opened_at is not None
            and self._clock.now() - self._opened_at >= self.reset_after
        ):
            self._state = CircuitState.HALF_OPEN
            self._trial_running = False
        return self._state

    def _admit(self) -> bool:
        """Raise when the call may not pass; return whether it is the half-open trial."""
        with self._lock:
            state = self._current()
            if state is CircuitState.OPEN:
                raise EmbeddingCircuitOpenError("the embedding provider circuit is open")
            if state is CircuitState.HALF_OPEN:
                if self._trial_running:
                    raise EmbeddingCircuitOpenError(
                        "the embedding provider circuit is half-open and a trial is running"
                    )
                self._trial_running = True
                return True
            return False

    def _record(self, *, failed: bool, trial: bool) -> None:
        with self._lock:
            if trial:
                self._trial_running = False
            if not failed:
                self._state, self._failures, self._opened_at = CircuitState.CLOSED, 0, None
                return
            self._failures += 1
            if trial or self._failures >= self.failure_threshold:
                self._state, self._failures, self._opened_at = CircuitState.OPEN, 0, self._clock.now()

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        trial = self._admit()
        try:
            batch = self.inner.embed(texts)
        except RetrievalBackendError as error:
            self._record(failed=error.retryable, trial=trial)
            raise
        except BaseException:
            self._record(failed=False, trial=trial)
            raise
        self._record(failed=False, trial=trial)
        return batch


class CostAccountingEmbedding(EmbeddingDecorator):
    """Prices every successful call (input tokens only) and records it in the ``bank.llm.cost_usd`` histogram with
    ``gen_ai.operation.name=embeddings``, so model spend stays one metric."""

    def __init__(self, inner: EmbeddingBackend, *, prices: PriceTable, telemetry: Telemetry) -> None:
        super().__init__(inner)
        self.prices = prices
        self._histogram = telemetry.histogram(COST_METRIC)

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        batch = self.inner.embed(texts)
        cost = self.prices.cost(batch.model_id, TokenUsage(input_tokens=batch.input_tokens))
        basis = self.prices.effective(batch.model_id).basis
        self._histogram.record(
            float(cost),
            {
                "gen_ai.response.model": batch.model_id,
                "gen_ai.operation.name": EMBEDDING_OPERATION,
                "bank.llm.price_basis": basis.value,
            },
        )
        return replace(batch, cost_usd=cost)
