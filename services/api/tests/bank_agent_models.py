"""Tiny hand-written model artifacts for the learned-adapter tests (fixtures, not trained models)."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_agent.adapters.models.resolver_features import FEATURE_NAMES
from bank_agent.adapters.retrieval.embedding import Vector
from bank_agent.domain.intelligence import ResolvedArtifact

TFIDF_ARTIFACT: dict[str, Any] = {
    "format": "tfidf_logreg/1",
    "analyzer": "router_terms@1",
    "classes": ["balance_inquiry", "card_block"],
    "vocabulary": ["w:saldo", "w:bloquear"],
    "idf": [1.0, 1.0],
    "weights": [[3.0, -3.0], [-3.0, 3.0]],
    "intercept": [0.0, 0.0],
    "temperature": 1.0,
    "threshold": 0.6,
}

EMBEDDING_ARTIFACT: dict[str, Any] = {
    "format": "embedding_logreg/1",
    "embedder": "fixture-embedder",
    "classes": ["balance_inquiry", "card_block"],
    "weights": [[4.0, 0.0], [0.0, 4.0]],
    "intercept": [0.0, 0.0],
    "temperature": 1.0,
    "threshold": 0.6,
}

_AMOUNT_REL = FEATURE_NAMES.index("amount_rel_diff")
_MERCHANT = FEATURE_NAMES.index("merchant_similarity")

LGBM_ARTIFACT: dict[str, Any] = {
    "format": "lgbm_ranker/1",
    "features": "resolver_features@1",
    "feature_names": list(FEATURE_NAMES),
    "trees": [
        {
            "feature": _AMOUNT_REL,
            "threshold": 0.01,
            "default_left": True,
            "missing": "none",
            "left": {"value": 2.0},
            "right": {"value": -1.0},
        },
        {
            "feature": _MERCHANT,
            "threshold": 0.7,
            "default_left": True,
            "missing": "none",
            "left": {"value": 0.0},
            "right": {"value": 1.5},
        },
    ],
    "margin": 0.3,
}


def publish(root: Path, name: str, artifact: dict[str, Any], alias: str | None = "champion") -> ResolvedArtifact:
    """Register ``artifact`` under ``name`` in a registry at ``root`` and optionally point ``alias`` at it."""
    store = FilesystemModelStore(root)
    resolved = store.register(name, artifact, {"source": "test fixture"})
    if alias is not None:
        store.set_alias(name, alias, resolved.ref.version, {"approved_by": "test"})
    return resolved


class FixtureEmbedder:
    """Maps texts mentioning a balance to (1, 0) and everything else to (0, 1)."""

    def __init__(self, model_id: str = "fixture-embedder") -> None:
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> Vector:
        return (1.0, 0.0) if "saldo" in text.lower() else (0.0, 1.0)
