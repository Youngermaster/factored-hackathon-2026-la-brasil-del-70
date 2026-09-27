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
    "null_score": -2.0,
}


_RANGES = [[300.0, 850.0], [0.0, 120.0], [1.0, 8.0], [0.0, 3.0]]


def _linear(product_weight: float, intercept: float) -> dict[str, Any]:
    return {
        "kind": "linear",
        "impute": [650.0, 36.0, 1.0, 0.5],
        "mean": [650.0, 36.0, 1.4, 0.5],
        "scale": [80.0, 20.0, 0.6, 0.3],
        "weights": [-0.1, 0.0, product_weight, 0.05],
        "missing_weights": [0.0, 0.0, 0.0, 0.1],
        "intercept": intercept,
    }


RISK_LOGREG_ARTIFACT: dict[str, Any] = {
    "format": "risk_classifier/1",
    "features": "risk_features@1",
    "feature_names": ["credit_score", "tenure_months", "credit_product_count", "utilization"],
    "label_definition": "snapshot_dpd30_any_credit_product",
    "scorer": _linear(0.5, -1.6),
    "calibrator": {"kind": "identity"},
    "interval": {
        "method": "bootstrap",
        "members": [
            {"scorer": _linear(0.45, -1.65), "calibrator": {"kind": "identity"}},
            {"scorer": _linear(0.55, -1.55), "calibrator": {"kind": "platt", "a": 1.0, "b": 0.0}},
            {"scorer": _linear(0.5, -1.6), "calibrator": {"kind": "identity"}},
        ],
        "lower": 0.025,
        "upper": 0.975,
    },
    "cut_medium": 0.2,
    "cut_high": 0.35,
    "ranges": _RANGES,
    "wide_width": 0.1,
}
"""A fixture: risk rises with the credit product count (about 0.12 for one product, 0.41 for three)."""

RISK_LGBM_ARTIFACT: dict[str, Any] = {
    **RISK_LOGREG_ARTIFACT,
    "scorer": {
        "kind": "trees",
        "trees": [
            {
                "feature": 2,
                "threshold": 1.5,
                "default_left": True,
                "missing": "nan",
                "left": {"value": -1.9},
                "right": {
                    "feature": 2,
                    "threshold": 2.5,
                    "default_left": True,
                    "missing": "nan",
                    "left": {"value": -1.2},
                    "right": {"value": -0.5},
                },
            }
        ],
    },
    "calibrator": {"kind": "isotonic", "x": [-1.9, -1.2, -0.5], "y": [0.12, 0.23, 0.38]},
    "interval": {"method": "venn_abers", "edges": [-1.5, -0.8], "p0": [0.11, 0.22, 0.36], "p1": [0.13, 0.25, 0.41]},
}
"""A fixture: one tree on the credit product count, isotonic calibration, and a three-bin Venn-Abers table."""


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
