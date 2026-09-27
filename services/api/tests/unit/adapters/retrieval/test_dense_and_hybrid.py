"""Dense retrieval on the deterministic fake embedder, the embedding cache, and hybrid fusion with floors."""

import sys
from pathlib import Path

import pytest

from bank_agent.adapters.retrieval.bm25 import Bm25Index, Bm25Retriever
from bank_agent.adapters.retrieval.dense import DenseIndex, DenseRetriever, model_version
from bank_agent.adapters.retrieval.embedding import (
    CachingEmbedder,
    SentenceTransformerEmbedder,
    dot,
    ml_extra_installed,
    normalize,
)
from bank_agent.adapters.retrieval.hybrid import FusionComponent, HybridRetriever
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import EmbeddingBackendUnavailableError, RetrievalIndexError
from bank_agent.domain.intelligence import RetrievalQuery
from bank_agent.domain.locale import Country, Language
from bank_agent_retrieval import FIXTURE_DOCUMENTS, HashingEmbedder


def query(text: str, language: Language = Language.ES, country: Country = Country.MX, k: int = 5) -> RetrievalQuery:
    return RetrievalQuery(text=UntrustedText(text), language=language, jurisdiction=country, k=k)


def dense() -> DenseRetriever:
    embedder = HashingEmbedder()
    return DenseRetriever(DenseIndex.build(FIXTURE_DOCUMENTS, embedder), embedder)


def test_dense_ranks_by_cosine_within_the_visible_documents() -> None:
    result = dense().search(query("bloqueo de tarjeta robada"))
    assert result.hits[0].clause.clause_id == "CRD-ALL-2"
    assert all(-1.0 <= hit.score <= 1.0 for hit in result.hits)
    assert {hit.clause.clause_id for hit in result.hits} <= {"DSP-MX-1", "CRD-ALL-2", "ACC-ALL-1"}
    assert result.retriever.name == "dense"
    assert result.retriever.version == "fixture.hashing"


def test_dense_skips_the_query_embedding_when_nothing_is_visible() -> None:
    embedder = HashingEmbedder()
    retriever = DenseRetriever(DenseIndex.build(FIXTURE_DOCUMENTS, embedder), embedder)
    assert retriever.search(query("window", language=Language.EN)).hits == ()
    assert embedder.query_calls == 0


def test_dense_refuses_an_index_from_another_model_or_a_short_vector_list() -> None:
    index = DenseIndex.build(FIXTURE_DOCUMENTS, HashingEmbedder(name="fixture/one"))
    with pytest.raises(RetrievalIndexError, match="another embedding model"):
        DenseRetriever(index, HashingEmbedder(name="fixture/two"))
    with pytest.raises(RetrievalIndexError, match="one vector per document"):
        DenseIndex(FIXTURE_DOCUMENTS, [], "fixture/one")


def test_model_version_is_a_valid_model_ref_version() -> None:
    assert model_version("intfloat/multilingual-e5-small|query: |passage: ") == "intfloat.multilingual-e5-small"
    assert model_version("///") == "unknown"


def test_vector_helpers() -> None:
    assert normalize([3.0, 4.0]) == (0.6, 0.8)
    assert normalize([0.0, 0.0]) == (0.0, 0.0)
    assert dot((0.6, 0.8), (0.6, 0.8)) == pytest.approx(1.0)


def test_the_cache_stores_vectors_by_content_hash(tmp_path: Path) -> None:
    inner = HashingEmbedder()
    cache = CachingEmbedder(inner, tmp_path)
    first = cache.embed_passages(["uno", "dos"])
    second = CachingEmbedder(inner, tmp_path).embed_passages(["dos", "uno", "tres"])
    assert second[:2] == [first[1], first[0]]
    assert inner.passage_calls == 2
    assert cache.model_id == inner.model_id
    assert cache.embed_query("plazo") == cache.embed_query("plazo")
    assert (cache.hits, cache.misses) == (1, 3)
    assert len(list(tmp_path.rglob("*.json"))) == 4
    assert CachingEmbedder(HashingEmbedder(name="fixture/other"), tmp_path).embed_query("plazo") is not None
    assert len(list(tmp_path.rglob("*.json"))) == 5


def test_a_missing_ml_extra_is_a_clear_configuration_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    with pytest.raises(EmbeddingBackendUnavailableError, match="extra ml"):
        SentenceTransformerEmbedder(cache_dir=tmp_path)
    assert isinstance(ml_extra_installed(), bool)


def test_hybrid_fuses_components_after_their_floors() -> None:
    bm25 = Bm25Retriever(Bm25Index.build(FIXTURE_DOCUMENTS))
    hybrid = HybridRetriever([FusionComponent(bm25, 0.0), FusionComponent(dense(), 0.0)], k=60)
    result = hybrid.search(query("bloqueo de tarjeta robada", k=2))
    assert result.hits[0].clause.clause_id == "CRD-ALL-2"
    assert result.hits[0].score == pytest.approx(2 / 61)
    assert len(result.hits) == 2
    assert result.retriever.name == "hybrid"


def test_hybrid_is_empty_when_no_component_clears_its_floor() -> None:
    bm25 = Bm25Retriever(Bm25Index.build(FIXTURE_DOCUMENTS))
    hybrid = HybridRetriever([FusionComponent(bm25, 1000.0), FusionComponent(dense(), 1.5)])
    assert hybrid.search(query("bloqueo de tarjeta robada")).hits == ()
    with pytest.raises(ValueError, match="at least one component"):
        HybridRetriever([])
