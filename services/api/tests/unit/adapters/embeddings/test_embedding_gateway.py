"""The hosted embedding gateway: the LiteLLM adapter with a fake ``litellm.embedding``, and every decorator."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import SecretStr

from bank_agent.adapters.embeddings.backend import (
    CircuitBreakingEmbedding,
    CircuitState,
    CostAccountingEmbedding,
    EmbeddingBatch,
    RetryingEmbedding,
)
from bank_agent.adapters.embeddings.gateway import GatewayEmbedder, RedactingEmbedder
from bank_agent.adapters.embeddings.litellm_embedding import LiteLLMEmbedding, map_embedding_error
from bank_agent.adapters.llm.cost import COST_METRIC
from bank_agent.adapters.llm.prices import ModelPrice, PriceTable, PriceTableFile
from bank_agent.adapters.llm.redaction import Redactor
from bank_agent.domain.errors import (
    EmbeddingCircuitOpenError,
    EmbeddingProviderError,
    EmbeddingRateLimitedError,
    EmbeddingRejectedError,
    EmbeddingTimeoutError,
    RetrievalBackendError,
)
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.telemetry import RecordingTelemetry

MODEL = "azure/text-embedding-3-small"
START = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


class FakeEmbeddingCall:
    """Stands in for ``litellm.embedding``: records the arguments and answers with vectors of the asked dimension."""

    def __init__(self, *, dimension: int = 4, error: Exception | None = None, shuffle: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.dimension = dimension
        self.error = error
        self.shuffle = shuffle

    def __call__(self, **arguments: Any) -> dict[str, Any]:
        self.calls.append(arguments)
        if self.error is not None:
            raise self.error
        texts = arguments["input"]
        data = [
            {"index": index, "embedding": [float(len(text) + index + 1)] + [1.0] * (self.dimension - 1)}
            for index, text in enumerate(texts)
        ]
        if self.shuffle:
            data.reverse()
        return {"data": data, "usage": {"prompt_tokens": 7 * len(texts)}}


class ProviderFailureError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__("the request quoted: my email is ana@example.com")
        self.status_code = status_code


class ScriptedBackend:
    """An ``EmbeddingBackend`` that fails with the scripted errors first, then succeeds."""

    def __init__(self, *errors: RetrievalBackendError) -> None:
        self.errors = list(errors)
        self.calls = 0

    @property
    def model_id(self) -> str:
        return MODEL

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return EmbeddingBatch(vectors=tuple((1.0, 0.0) for _ in texts), input_tokens=10 * len(texts), model_id=MODEL)


def _adapter(call: FakeEmbeddingCall, *, dimensions: int | None = 4) -> LiteLLMEmbedding:
    return LiteLLMEmbedding(
        MODEL,
        api_key=SecretStr("k" * 40),
        api_base="https://example.openai.azure.com/",
        timeout_seconds=3.0,
        dimensions=dimensions,
        embedding=call,
    )


# --- LiteLLM adapter ----------------------------------------------------------------------------------------


def _state(breaker: CircuitBreakingEmbedding) -> CircuitState:
    """Read through a function so the type checker does not narrow the property between calls."""
    return breaker.state


def test_passes_model_key_base_timeout_and_dimensions_with_provider_retries_off() -> None:
    call = FakeEmbeddingCall()
    batch = _adapter(call).embed(["uno", "dos"])

    arguments = call.calls[0]
    assert arguments["model"] == MODEL
    assert arguments["input"] == ["uno", "dos"]
    assert arguments["timeout"] == 3.0
    assert arguments["max_retries"] == 0
    assert arguments["dimensions"] == 4
    assert arguments["api_base"] == "https://example.openai.azure.com/"
    assert arguments["api_key"] == "k" * 40
    assert batch.input_tokens == 14
    assert batch.model_id == MODEL
    assert len(batch.vectors) == 2


def test_the_model_id_names_the_dimension_so_caches_never_mix_sizes() -> None:
    assert _adapter(FakeEmbeddingCall()).model_id == f"{MODEL}|4"
    assert _adapter(FakeEmbeddingCall(), dimensions=None).model_id == MODEL


def test_keeps_input_order_when_the_provider_answers_out_of_order() -> None:
    batch = _adapter(FakeEmbeddingCall(shuffle=True)).embed(["a", "bbb"])

    assert [vector[0] for vector in batch.vectors] == [2.0, 5.0]


def test_refuses_vectors_of_another_dimension_than_configured() -> None:
    with pytest.raises(EmbeddingProviderError):
        _adapter(FakeEmbeddingCall(dimension=3)).embed(["a"])


@pytest.mark.parametrize(
    ("status", "expected", "retryable"),
    [
        (408, EmbeddingTimeoutError, True),
        (504, EmbeddingTimeoutError, True),
        (429, EmbeddingRateLimitedError, True),
        (401, EmbeddingRejectedError, False),
        (404, EmbeddingRejectedError, False),
        (500, EmbeddingProviderError, True),
    ],
)
def test_maps_provider_failures_by_status_without_quoting_the_request(
    status: int, expected: type[RetrievalBackendError], retryable: bool
) -> None:
    with pytest.raises(expected) as raised:
        _adapter(FakeEmbeddingCall(error=ProviderFailureError(status))).embed(["a"])

    assert raised.value.retryable is retryable
    assert "example.com" not in str(raised.value)
    assert raised.value.__cause__ is None


def test_a_timeout_class_is_a_timeout() -> None:
    assert isinstance(map_embedding_error(TimeoutError()), EmbeddingTimeoutError)


def test_an_empty_batch_makes_no_call() -> None:
    call = FakeEmbeddingCall()
    assert _adapter(call).embed([]).vectors == ()
    assert call.calls == []


# --- Gateway embedder and redaction -----------------------------------------------------------------------------


def test_batches_passages_and_returns_unit_vectors() -> None:
    call = FakeEmbeddingCall()
    embedder = GatewayEmbedder(_adapter(call), batch_size=2)

    vectors = embedder.embed_passages(["a", "b", "c"])

    assert [len(c["input"]) for c in call.calls] == [2, 1]
    assert all(sum(value * value for value in vector) == pytest.approx(1.0) for vector in vectors)
    assert embedder.model_id == f"{MODEL}|4"


def test_redacts_the_query_but_not_the_policy_passages() -> None:
    call = FakeEmbeddingCall()
    embedder = RedactingEmbedder(GatewayEmbedder(_adapter(call)), redactor=Redactor())

    embedder.embed_query("Mi correo es ana.perez@example.com y mi tarjeta 4111 1111 1111 1111")
    embedder.embed_passages(["Tienes 90 días para disputar un cargo."])

    sent_query = call.calls[0]["input"][0]
    assert "ana.perez@example.com" not in sent_query
    assert "4111" not in sent_query
    assert call.calls[1]["input"] == ["Tienes 90 días para disputar un cargo."]


def test_a_zero_vector_is_a_provider_error() -> None:
    class ZeroBackend(ScriptedBackend):
        def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
            return EmbeddingBatch(vectors=((0.0, 0.0),), input_tokens=1, model_id=MODEL)

    with pytest.raises(EmbeddingProviderError):
        GatewayEmbedder(ZeroBackend()).embed_query("hola")


# --- Retry ------------------------------------------------------------------------------------------------------


def test_retries_transient_failures_with_bounded_backoff() -> None:
    sleeps: list[float] = []
    backend = ScriptedBackend(EmbeddingTimeoutError("slow"))
    retrying = RetryingEmbedding(backend, max_retries=1, sleep=sleeps.append, jitter=lambda: 0.0)

    retrying.embed(["a"])

    assert backend.calls == 2
    assert sleeps == [pytest.approx(0.1)]


def test_never_retries_a_rejection_and_stops_after_the_limit() -> None:
    rejected = ScriptedBackend(EmbeddingRejectedError("no deployment"))
    with pytest.raises(EmbeddingRejectedError):
        RetryingEmbedding(rejected, sleep=lambda _: None).embed(["a"])
    assert rejected.calls == 1

    flaky = ScriptedBackend(EmbeddingProviderError("1"), EmbeddingProviderError("2"), EmbeddingProviderError("3"))
    with pytest.raises(EmbeddingProviderError):
        RetryingEmbedding(flaky, max_retries=2, sleep=lambda _: None).embed(["a"])
    assert flaky.calls == 3


def test_refuses_more_retries_than_allowed() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        RetryingEmbedding(ScriptedBackend(), max_retries=3)


# --- Circuit breaker --------------------------------------------------------------------------------------------


def test_opens_after_consecutive_transient_failures_and_probes_after_the_reset() -> None:
    clock = FixedClock(START)
    backend = ScriptedBackend(EmbeddingProviderError("1"), EmbeddingProviderError("2"))
    breaker = CircuitBreakingEmbedding(backend, clock=clock, failure_threshold=2, reset_after=timedelta(seconds=30))

    for _ in range(2):
        with pytest.raises(EmbeddingProviderError):
            breaker.embed(["a"])
    assert _state(breaker) is CircuitState.OPEN
    with pytest.raises(EmbeddingCircuitOpenError):
        breaker.embed(["a"])
    assert backend.calls == 2

    clock.advance(timedelta(seconds=30))
    assert _state(breaker) is CircuitState.HALF_OPEN
    breaker.embed(["a"])
    assert _state(breaker) is CircuitState.CLOSED


def test_a_failed_trial_opens_the_circuit_again() -> None:
    clock = FixedClock(START)
    backend = ScriptedBackend(EmbeddingTimeoutError("1"), EmbeddingTimeoutError("2"))
    breaker = CircuitBreakingEmbedding(backend, clock=clock, failure_threshold=1, reset_after=timedelta(seconds=5))

    with pytest.raises(EmbeddingTimeoutError):
        breaker.embed(["a"])
    clock.advance(timedelta(seconds=5))
    with pytest.raises(EmbeddingTimeoutError):
        breaker.embed(["a"])
    assert _state(breaker) is CircuitState.OPEN


def test_a_rejection_counts_as_reachable() -> None:
    backend = ScriptedBackend(EmbeddingRejectedError("1"), EmbeddingRejectedError("2"))
    breaker = CircuitBreakingEmbedding(backend, clock=FixedClock(START), failure_threshold=1)

    for _ in range(2):
        with pytest.raises(EmbeddingRejectedError):
            breaker.embed(["a"])
    assert _state(breaker) is CircuitState.CLOSED


# --- Cost accounting --------------------------------------------------------------------------------------------


def test_prices_input_tokens_and_records_the_cost_as_model_spend() -> None:
    prices = PriceTable(
        PriceTableFile(
            schema_version=1,
            currency="USD",
            unverified_price_multiplier=Decimal("1.5"),
            models=(
                ModelPrice(
                    model_id=MODEL,
                    input_usd_per_million=Decimal("0.022"),
                    output_usd_per_million=Decimal(0),
                    effective_date=START.date(),
                    source_url="https://prices.azure.com/api/retail/prices",
                    verified=True,
                ),
            ),
        )
    )
    telemetry = RecordingTelemetry()
    accounted = CostAccountingEmbedding(ScriptedBackend(), prices=prices, telemetry=telemetry)

    batch = accounted.embed(["a"] * 100)

    assert batch.cost_usd == Decimal("0.000022")
    value, attributes = telemetry.histograms[COST_METRIC].values[0]
    assert value == pytest.approx(0.000022)
    assert attributes["gen_ai.operation.name"] == "embeddings"
    assert attributes["gen_ai.response.model"] == MODEL
