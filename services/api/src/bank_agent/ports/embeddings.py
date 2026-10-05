"""Text embedding port (dense retrieval, ADR 0012; hosted embeddings for the Qdrant index, ADR 0047)."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.vectors import Vector


class Embedder(Protocol):
    """Turns texts into vectors for similarity search.

    Preconditions: passages are policy text from the synthetic pack; a query is customer text, untrusted, and a
    hosted implementation redacts it before it leaves the process.
    Postconditions: one vector per text, in order, all of the same dimension; ``model_id`` names the model and
    every option that changes the vectors (prefixes, dimensions), so caches and indexes key on it.
    Errors: a local model raises ``EmbeddingBackendUnavailableError`` when its optional extra is missing; a hosted
    model raises only the ``RetrievalBackendError`` family (timeout, rate limited, provider error, rejected,
    circuit open), which the retrieval fallback turns into a BM25 answer.
    Isolation: implementations never receive customer identifiers; only the query text is sent, redacted.
    """

    @property
    def model_id(self) -> str: ...

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]: ...

    def embed_query(self, text: str) -> Vector: ...
