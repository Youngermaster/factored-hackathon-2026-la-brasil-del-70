"""The TF-IDF and embedding routers on hand-written artifacts, and the shared text analyzer."""

import math
from pathlib import Path

import pytest

from bank_agent.adapters.models.embedding_router import EmbeddingIntentRouter
from bank_agent.adapters.models.registry import FilesystemModelRegistry
from bank_agent.adapters.models.text_features import normalize, router_terms, softmax, tfidf_vector, tokens
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import ModelArtifactIntegrityError, ModelUnavailableError
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent
from bank_agent_models import EMBEDDING_ARTIFACT, TFIDF_ARTIFACT, FixtureEmbedder, publish


def test_the_analyzer_folds_masks_digits_and_emits_words_bigrams_and_character_grams() -> None:
    assert normalize("Cartão  1234 BLOQUEADO") == "cartao # bloqueado"
    assert tokens("¿Mi saldo, 250?") == ["mi", "saldo", "#"]
    terms = router_terms("Mi saldo")
    assert {"w:mi", "w:saldo", "w:mi_saldo", "c: m", "c:mi s", "c:do "} <= set(terms)
    assert router_terms("") == ["c:  "]


def test_tfidf_vector_is_sublinear_and_l2_normalized() -> None:
    vector = tfidf_vector("saldo saldo bloquear", {"w:saldo": 0, "w:bloquear": 1}, [1.0, 2.0])
    raw = [1.0 + math.log(2), 2.0]
    norm = math.hypot(*raw)
    assert vector == pytest.approx({0: raw[0] / norm, 1: raw[1] / norm})
    assert tfidf_vector("nada", {"w:saldo": 0}, [1.0]) == {}


def test_softmax_is_stable_and_tempered() -> None:
    assert softmax([1000.0, 1000.0]) == pytest.approx([0.5, 0.5])
    assert softmax([2.0, 0.0], temperature=2.0) == pytest.approx(softmax([1.0, 0.0]))


def test_tfidf_router_routes_and_applies_the_stored_threshold(tmp_path: Path) -> None:
    resolved = publish(tmp_path, "router:tfidf", TFIDF_ARTIFACT)
    router = TfidfIntentRouter.load(FilesystemModelRegistry(tmp_path).resolve("router:tfidf", "champion"))
    balance = router.route(UntrustedText("¿Cuál es mi saldo?"), Language.ES)
    assert balance.intent is Intent.BALANCE_INQUIRY
    assert balance.model == resolved.ref
    assert balance.below_threshold is False
    assert [candidate.intent for candidate in balance.candidates] == [Intent.BALANCE_INQUIRY, Intent.CARD_BLOCK]
    unknown = router.route(UntrustedText("hola"), Language.ES)
    assert unknown.confidence == pytest.approx(0.5)
    assert unknown.below_threshold is True
    assert router.threshold == 0.6


@pytest.mark.parametrize(
    "change",
    [
        {"analyzer": "other@1"},
        {"intercept": [0.0]},
        {"idf": [1.0]},
        {"weights": [[1.0], [1.0]]},
        {"classes": ["balance_inquiry", "balance_inquiry"]},
    ],
)
def test_malformed_tfidf_artifacts_are_refused(tmp_path: Path, change: dict[str, object]) -> None:
    resolved = publish(tmp_path, "router:tfidf", {**TFIDF_ARTIFACT, **change})
    with pytest.raises(ModelArtifactIntegrityError):
        TfidfIntentRouter.load(resolved)


def test_embedding_router_needs_its_embedder(tmp_path: Path) -> None:
    resolved = publish(tmp_path, "router:embeddings", EMBEDDING_ARTIFACT)
    router = EmbeddingIntentRouter.load(resolved, FixtureEmbedder())
    assert router.route(UntrustedText("mi saldo"), Language.ES).intent is Intent.BALANCE_INQUIRY
    assert router.route(UntrustedText("bloquear"), Language.ES).intent is Intent.CARD_BLOCK
    assert router.threshold == 0.6
    with pytest.raises(ModelUnavailableError):
        EmbeddingIntentRouter.load(resolved, None)
    with pytest.raises(ModelUnavailableError):
        EmbeddingIntentRouter.load(resolved, FixtureEmbedder("another-model"))


def test_malformed_embedding_artifacts_are_refused(tmp_path: Path) -> None:
    bad = publish(tmp_path, "router:embeddings", {**EMBEDDING_ARTIFACT, "weights": [[1.0, 0.0], [1.0]]})
    with pytest.raises(ModelArtifactIntegrityError):
        EmbeddingIntentRouter.load(bad, FixtureEmbedder())
    short = publish(tmp_path, "router:embeddings", {**EMBEDDING_ARTIFACT, "intercept": [0.0]}, alias=None)
    with pytest.raises(ModelArtifactIntegrityError):
        EmbeddingIntentRouter.load(short, FixtureEmbedder())
