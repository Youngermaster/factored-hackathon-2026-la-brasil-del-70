"""``router:embeddings``: multilingual sentence embeddings with a logistic regression head.

The head (class-major weights over the embedding dimensions, intercepts, temperature, threshold) is a JSON artifact.
The encoder is the ``Embedder`` of the retrieval adapters, which needs the optional ``ml`` extra
(sentence-transformers). ``load`` raises ``ModelUnavailableError`` when the extra is absent or the artifact names
another encoder, so the composition root can fall back to the rule baseline instead of failing a turn.
"""

from collections.abc import Sequence
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from bank_agent.adapters.models.registry import read_verified
from bank_agent.adapters.models.tfidf_router import LinearHead
from bank_agent.adapters.retrieval.embedding import Embedder
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import ModelArtifactIntegrityError, ModelUnavailableError
from bank_agent.domain.intelligence import IntentPrediction, ModelRef, ResolvedArtifact
from bank_agent.domain.locale import Language


class EmbeddingRouterArtifact(LinearHead):
    format: Literal["embedding_logreg/1"]
    embedder: Annotated[str, Field(min_length=1, max_length=300)]
    """The ``Embedder.model_id`` the head was trained on (model name and prefixes)."""
    weights: tuple[tuple[float, ...], ...]
    """Class-major: ``weights[class][dimension]``."""

    @model_validator(mode="after")
    def _shapes(self) -> Self:
        if not (len(self.intercept) == len(self.classes) == len(self.weights)):
            raise ValueError("one intercept and one weight row per class")
        if len({len(row) for row in self.weights}) != 1:
            raise ValueError("every class needs the same number of dimensions")
        return self


class EmbeddingIntentRouter:
    """Implements ``IntentRouter`` from an ``embedding_logreg/1`` artifact and a matching embedder."""

    def __init__(self, artifact: EmbeddingRouterArtifact, embedder: Embedder, model: ModelRef) -> None:
        if embedder.model_id != artifact.embedder:
            raise ModelUnavailableError(f"artifact needs embedder {artifact.embedder}, got {embedder.model_id}")
        self._artifact = artifact
        self._embedder = embedder
        self.model = model

    @classmethod
    def load(cls, resolved: ResolvedArtifact, embedder: Embedder | None) -> "EmbeddingIntentRouter":
        try:
            artifact = EmbeddingRouterArtifact.model_validate(read_verified(resolved))
        except ValueError as error:
            raise ModelArtifactIntegrityError(f"artifact {resolved.ref} is not a valid embedding router") from error
        if embedder is None:
            raise ModelUnavailableError("router:embeddings needs the ml extra: uv sync --all-packages --extra ml")
        return cls(artifact, embedder, resolved.ref)

    @property
    def threshold(self) -> float:
        return self._artifact.threshold

    def logits_for(self, vector: Sequence[float]) -> list[float]:
        artifact = self._artifact
        return [
            bias + sum(weight * value for weight, value in zip(row, vector, strict=True))
            for bias, row in zip(artifact.intercept, artifact.weights, strict=True)
        ]

    def route(self, text: UntrustedText, language: Language) -> IntentPrediction:
        return self._artifact.predict(self.logits_for(self._embedder.embed_query(text)), self.model)
