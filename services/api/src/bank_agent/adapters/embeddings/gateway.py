"""The ``Embedder`` port over an ``EmbeddingBackend``, and the redaction decorator for query text.

Passages are policy clauses from the synthetic pack: team-written, public, and free of customer data, so they are
embedded as written (redacting them would change their figures). A query is customer text; ``RedactingEmbedder``
masks emails, document numbers, card and phone numbers, long digit runs, and introduced names (the language model
gateway's ``Redactor``) before it reaches the backend, so nothing below it sees the original text (CLAUDE.md rule 6).
"""

import math
from collections.abc import Sequence
from typing import Final

from bank_agent.adapters.embeddings.backend import EmbeddingBackend
from bank_agent.adapters.llm.redaction import Redactor
from bank_agent.domain.errors import EmbeddingProviderError
from bank_agent.domain.vectors import Vector
from bank_agent.ports.embeddings import Embedder

DEFAULT_BATCH_SIZE: Final = 64


def _unit(vector: Sequence[float]) -> Vector:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        raise EmbeddingProviderError("the embedding provider returned a zero vector")
    return tuple(value / norm for value in vector)


class GatewayEmbedder:
    """Implements ``Embedder`` over a backend: batches of at most ``batch_size`` texts, unit vectors out."""

    def __init__(self, backend: EmbeddingBackend, *, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        if batch_size < 1:
            raise ValueError("the batch size must be positive")
        self._backend = backend
        self._batch_size = batch_size

    @property
    def model_id(self) -> str:
        return self._backend.model_id

    def _embed(self, texts: Sequence[str]) -> list[Vector]:
        vectors: list[Vector] = []
        for start in range(0, len(texts), self._batch_size):
            batch = self._backend.embed(texts[start : start + self._batch_size])
            vectors.extend(_unit(vector) for vector in batch.vectors)
        if len({len(vector) for vector in vectors}) > 1:
            raise EmbeddingProviderError("the embedding provider returned vectors of different dimensions")
        return vectors

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        return self._embed(list(texts))

    def embed_query(self, text: str) -> Vector:
        return self._embed([text])[0]


class RedactingEmbedder:
    """``Embedder`` decorator: queries are redacted before they leave the process; passages pass unchanged."""

    def __init__(self, inner: Embedder, *, redactor: Redactor) -> None:
        self._inner = inner
        self._redactor = redactor

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        return self._inner.embed_passages(texts)

    def embed_query(self, text: str) -> Vector:
        return self._inner.embed_query(self._redactor.redact_text(text))
