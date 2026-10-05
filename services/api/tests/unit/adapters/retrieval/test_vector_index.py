"""The clause collection in a vector store, the retriever over it, and the BM25 fallback (ADR 0047).

Everything runs over the in-memory vector store and the deterministic hashing embedder (fixtures); the Qdrant
adapter passes the same store contract in ``tests/contracts``.
"""

import uuid

import pytest

from bank_agent.adapters.retrieval.bm25 import Bm25Index, Bm25Retriever
from bank_agent.adapters.retrieval.dense import DenseIndex, DenseRetriever
from bank_agent.adapters.retrieval.fallback import FALLBACK_METRIC, FallbackRetriever
from bank_agent.adapters.retrieval.vector_index import (
    KEYWORD_FIELDS,
    POINT_NAMESPACE,
    VectorClauseIndex,
    VectorRetriever,
    collection_name,
    model_version,
    point_id,
    workflow_of,
)
from bank_agent.adapters.vector.memory import InMemoryVectorStore
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import (
    EmbeddingTimeoutError,
    RetrievalBackendError,
    VectorCollectionMissingError,
    VectorStoreError,
)
from bank_agent.domain.intelligence import RetrievalQuery, RetrievalResult
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.policy import ClauseFamily
from bank_agent.domain.vectors import PayloadFilter, VectorPoint
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_retrieval import FIXTURE_DOCUMENTS, HashingEmbedder

PACK = "pack-fixture0001"


def query(text: str, language: Language = Language.ES, country: Country = Country.MX, k: int = 5) -> RetrievalQuery:
    return RetrievalQuery(text=UntrustedText(text), language=language, jurisdiction=country, k=k)


def indexed() -> tuple[InMemoryVectorStore, HashingEmbedder, VectorClauseIndex]:
    store, embedder = InMemoryVectorStore(), HashingEmbedder()
    clauses = VectorClauseIndex(store, embedder, pack_version=PACK)
    clauses.build(FIXTURE_DOCUMENTS)
    return store, embedder, clauses


class FailingRetriever:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        raise self.error


def test_names_the_collection_after_the_pack_and_the_embedding_model() -> None:
    name = collection_name("pack-be521e1d5bc3b63f", "azure/text-embedding-3-small|512")
    assert name == "policy-clauses-pack-be521e1d5bc3b63f-azure-text-embedding-3-small-512"
    assert model_version("azure/text-embedding-3-small|512") == "azure.text-embedding-3-small.512"


def test_point_ids_are_uuid5_of_the_clause_key_so_indexing_is_idempotent() -> None:
    document = FIXTURE_DOCUMENTS[0]
    assert point_id(document) == uuid.uuid5(POINT_NAMESPACE, "DSP-MX-1@1:es")
    assert len({point_id(d) for d in FIXTURE_DOCUMENTS}) == len(FIXTURE_DOCUMENTS)
    store, _, clauses = indexed()
    report = clauses.build(FIXTURE_DOCUMENTS)
    assert report.created is False
    assert report.points == len(FIXTURE_DOCUMENTS)
    assert store.list_collections() == (clauses.name,)


def test_the_payload_holds_keyword_fields_only_never_the_clause_text() -> None:
    store, embedder, clauses = indexed()
    vector = embedder.embed_query("bloqueo de tarjeta")
    matches = store.search(clauses.name, vector, limit=10, where=PayloadFilter())
    for match in matches:
        assert set(match.payload) == {"clause_id", "version", "language", "jurisdiction", "family", "workflow"}
        assert set(KEYWORD_FIELDS) <= set(match.payload)
        assert all("fixture" not in str(value) for value in match.payload.values())
    assert {match.payload["workflow"] for match in matches} == {"dispute", "card_support", "account_inquiry"}
    assert workflow_of(ClauseFamily.SCOPE) == "shared"


def test_ranks_like_the_in_process_dense_retriever_on_the_same_embeddings() -> None:
    store, embedder, clauses = indexed()
    vector = VectorRetriever(store, embedder, collection=clauses.name)
    dense = DenseRetriever(DenseIndex.build(FIXTURE_DOCUMENTS, embedder), embedder)
    for case in (query("bloqueo de tarjeta robada"), query("cartao roubado", Language.PT), query("plazo", k=2)):
        expected = [(hit.clause, round(hit.score, 6)) for hit in dense.search(case).hits]
        got = vector.search(case)
        assert [(hit.clause, round(hit.score, 6)) for hit in got.hits] == expected
        assert [hit.rank for hit in got.hits] == list(range(1, len(got.hits) + 1))
    assert str(vector.model) == "retriever:qdrant@fixture.hashing.q.p"


def test_filters_by_language_and_jurisdiction_before_ranking() -> None:
    store, embedder, clauses = indexed()
    retriever = VectorRetriever(store, embedder, collection=clauses.name)
    colombia = {hit.clause.clause_id for hit in retriever.search(query("plazo de mexico", country=Country.CO)).hits}
    assert colombia == {"DSP-CO-1", "CRD-ALL-2", "ACC-ALL-1"}
    portuguese = {hit.clause.clause_id for hit in retriever.search(query("prazo", Language.PT)).hits}
    assert portuguese == {"CRD-ALL-2", "DSP-MX-1"}
    assert retriever.search(query("window", Language.EN)).hits == ()


def test_check_reports_a_missing_or_incomplete_collection() -> None:
    store, embedder = InMemoryVectorStore(), HashingEmbedder()
    clauses = VectorClauseIndex(store, embedder, pack_version=PACK)
    with pytest.raises(VectorCollectionMissingError, match="does not exist"):
        clauses.check(6)
    clauses.build(FIXTURE_DOCUMENTS[:2])
    with pytest.raises(VectorCollectionMissingError, match="has 2 points, not 6"):
        clauses.check(6)
    with pytest.raises(VectorStoreError):
        clauses.build(())


def test_a_match_without_a_clause_reference_is_a_store_error() -> None:
    store, embedder = InMemoryVectorStore(), HashingEmbedder()
    store.ensure_collection("c", dimension=64, keyword_fields=())
    vector = embedder.embed_query("saldo")
    store.upsert(
        "c", [VectorPoint(id=uuid.UUID(int=1), vector=vector, payload={"language": "es", "jurisdiction": "MX"})]
    )
    with pytest.raises(VectorStoreError, match="no clause id"):
        VectorRetriever(store, embedder, collection="c").search(query("saldo"))


def test_falls_back_to_bm25_on_a_backend_error_and_counts_it() -> None:
    telemetry = RecordingTelemetry()
    bm25 = Bm25Retriever(Bm25Index.build(FIXTURE_DOCUMENTS))
    store, embedder, clauses = indexed()
    configured = VectorRetriever(store, embedder, collection=clauses.name).model
    for error in (EmbeddingTimeoutError("t"), VectorStoreError("s"), VectorCollectionMissingError("m")):
        retriever = FallbackRetriever(FailingRetriever(error), bm25, telemetry=telemetry, model=configured)
        result = retriever.search(query("bloqueo de tarjeta robada"))
        assert str(result.retriever) == "retriever:bm25@1"
        assert result.hits[0].clause.clause_id == "CRD-ALL-2"
    recorded = [attributes["error.type"] for _, attributes in telemetry.counters[FALLBACK_METRIC].points]
    assert recorded == ["embedding_timeout", "vector_store_error", "vector_collection_missing"]


def test_serves_the_primary_when_it_works_and_never_hides_programming_errors() -> None:
    telemetry = RecordingTelemetry()
    bm25 = Bm25Retriever(Bm25Index.build(FIXTURE_DOCUMENTS))
    store, embedder, clauses = indexed()
    primary = VectorRetriever(store, embedder, collection=clauses.name)
    served = FallbackRetriever(primary, bm25, telemetry=telemetry, model=primary.model).search(query("saldo"))
    assert served.retriever == primary.model
    broken = FallbackRetriever(FailingRetriever(ValueError("bug")), bm25, telemetry=telemetry, model=primary.model)
    with pytest.raises(ValueError, match="bug"):
        broken.search(query("saldo"))
    assert issubclass(VectorCollectionMissingError, RetrievalBackendError)
