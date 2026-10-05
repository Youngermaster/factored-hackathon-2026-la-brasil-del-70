"""LiteLLM's embedding API as an ``EmbeddingBackend`` (the hosted model: Azure OpenAI text-embedding-3-small).

LiteLLM is the optional ``litellm`` extra the API image already installs; it is imported on the first call. Each
call passes the model, key, base, timeout, and dimensions explicitly, with LiteLLM's own retries off: the gateway's
decorators own retries and the circuit. Failures map by HTTP status, as in the language model adapter: 408, 504, or a
timeout class become ``EmbeddingTimeoutError``, 429 ``EmbeddingRateLimitedError``, any other 4xx
``EmbeddingRejectedError`` (never retried), and everything else ``EmbeddingProviderError``. The provider exception
is not chained, because its text may quote the request.
"""

import os
from collections.abc import Callable, Sequence
from typing import Any

from pydantic import SecretStr

from bank_agent.adapters.embeddings.backend import EmbeddingBatch
from bank_agent.domain.errors import (
    EmbeddingProviderError,
    EmbeddingRateLimitedError,
    EmbeddingRejectedError,
    EmbeddingTimeoutError,
    RetrievalBackendError,
)

EmbeddingCall = Callable[..., Any]


def load_litellm_embedding() -> EmbeddingCall:
    """Import LiteLLM with its bundled model map and return ``litellm.embedding``."""
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    try:
        import litellm  # optional extra, imported on first use
    except ImportError:
        raise EmbeddingRejectedError("the litellm extra is not installed") from None
    litellm.telemetry = False
    embedding: EmbeddingCall = litellm.embedding
    return embedding


def map_embedding_error(error: Exception) -> RetrievalBackendError:
    status = getattr(error, "status_code", None)
    name = type(error).__name__
    detail = f"embedding call failed: {name}" + (f" (status {status})" if isinstance(status, int) else "")
    if isinstance(error, TimeoutError) or "Timeout" in name or status in (408, 504):
        return EmbeddingTimeoutError(detail)
    if status == 429 or "RateLimit" in name:
        return EmbeddingRateLimitedError(detail)
    if isinstance(status, int) and 400 <= status < 500:
        return EmbeddingRejectedError(detail)
    return EmbeddingProviderError(detail)


def _field(item: Any, name: str) -> Any:
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def parse_response(response: Any, expected: int) -> tuple[tuple[tuple[float, ...], ...], int]:
    """The vectors in input order and the input token count; anything malformed is a provider error."""
    data = _field(response, "data")
    if not isinstance(data, list) or len(data) != expected:
        raise EmbeddingProviderError("the embedding response has the wrong number of vectors")
    ordered: list[tuple[float, ...] | None] = [None] * expected
    for position, item in enumerate(data):
        index = _field(item, "index")
        slot = index if isinstance(index, int) and 0 <= index < expected else position
        values = _field(item, "embedding")
        if not isinstance(values, list) or not values:
            raise EmbeddingProviderError("the embedding response has an empty vector")
        ordered[slot] = tuple(float(value) for value in values)
    if any(vector is None for vector in ordered):
        raise EmbeddingProviderError("the embedding response repeats an index")
    usage = _field(response, "usage")
    tokens = _field(usage, "prompt_tokens") if usage is not None else None
    return tuple(vector for vector in ordered if vector is not None), int(tokens or 0)


class LiteLLMEmbedding:
    """One ``litellm.embedding`` call per batch for one configured model and dimension."""

    def __init__(
        self,
        model: str,
        *,
        api_key: SecretStr | None,
        api_base: str | None,
        timeout_seconds: float,
        dimensions: int | None = None,
        embedding: EmbeddingCall | None = None,
    ) -> None:
        if not model:
            raise EmbeddingRejectedError("no embedding model is configured")
        if timeout_seconds <= 0:
            raise ValueError("the timeout must be positive")
        self._model = model
        self._api_key = api_key
        self._api_base = api_base or None
        self._timeout_seconds = timeout_seconds
        self._dimensions = dimensions
        self._embedding = embedding

    @property
    def model_id(self) -> str:
        """The configured id plus the dimension, so caches and collections never mix vector sizes."""
        return f"{self._model}|{self._dimensions}" if self._dimensions else self._model

    @property
    def configured_model(self) -> str:
        return self._model

    def _arguments(self, texts: Sequence[str]) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "model": self._model,
            "input": list(texts),
            "timeout": self._timeout_seconds,
            "max_retries": 0,
        }
        if self._dimensions:
            arguments["dimensions"] = self._dimensions
        if self._api_key is not None:
            arguments["api_key"] = self._api_key.get_secret_value()
        if self._api_base is not None:
            arguments["api_base"] = self._api_base
        return arguments

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        if not texts:
            return EmbeddingBatch(vectors=(), input_tokens=0, model_id=self._model)
        embedding = self._embedding or load_litellm_embedding()
        try:
            response = embedding(**self._arguments(texts))
        except RetrievalBackendError:
            raise
        except Exception as error:  # every provider failure becomes a typed retrieval backend error
            raise map_embedding_error(error) from None
        vectors, tokens = parse_response(response, len(texts))
        if self._dimensions and any(len(vector) != self._dimensions for vector in vectors):
            raise EmbeddingProviderError("the embedding response has another dimension than configured")
        # Priced under the configured id (the price table keys on it), not the dimension-qualified one.
        return EmbeddingBatch(vectors=vectors, input_tokens=tokens, model_id=self._model)
