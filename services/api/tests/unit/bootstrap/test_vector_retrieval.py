"""Composition of the Qdrant retrievers (ADR 0047): selection by settings, the BM25 fallback, the hosted embedding
gateway, and the production rules. The vector store is the in-memory fake and the embedder the hashing fixture."""

from collections.abc import Sequence

import pytest

from bank_agent.adapters.embeddings.backend import EmbeddingBatch
from bank_agent.adapters.llm.cost import COST_METRIC
from bank_agent.adapters.retrieval.corpus import build_corpus
from bank_agent.adapters.retrieval.fallback import FALLBACK_METRIC
from bank_agent.adapters.retrieval.vector_index import VectorClauseIndex
from bank_agent.adapters.vector.memory import InMemoryVectorStore
from bank_agent.bootstrap.embeddings import build_hosted_embedder
from bank_agent.bootstrap.retrieval import (
    VectorRetrieval,
    build_grounding,
    build_retriever,
    build_vector_retrieval,
)
from bank_agent.bootstrap.settings import LLMSettings, RetrievalSettings, RetrieverName
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import RetrievalIndexError
from bank_agent.domain.intelligence import RetrievalQuery
from bank_agent.domain.locale import Country, Language
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_policy import NOW
from bank_agent_retrieval import HashingEmbedder
from bank_agent_workflows import shared_policy

MODEL = "azure/text-embedding-3-small"


def card_query(language: Language = Language.ES) -> RetrievalQuery:
    text = "me robaron la tarjeta, como la bloqueo" if language is Language.ES else "roubaram meu cartao, como bloqueio"
    return RetrievalQuery(text=UntrustedText(text), language=language, jurisdiction=Country.MX, k=3)


def vectors(*, built: bool = True) -> VectorRetrieval:
    policy, _ = shared_policy()
    store, embedder = InMemoryVectorStore(), HashingEmbedder()
    if built:
        VectorClauseIndex(store, embedder, pack_version=policy.repository.pack_version()).build(
            build_corpus(policy.repository)
        )
    return VectorRetrieval(store=store, embedder=embedder, telemetry=RecordingTelemetry())


def test_selects_the_qdrant_retriever_and_answers_from_the_collection() -> None:
    policy, _ = shared_policy()
    grounding = build_grounding(RetrievalSettings(retriever="qdrant"), policy.repository, vectors=vectors())
    result = grounding.retriever.search(card_query())
    assert str(result.retriever) == "retriever:qdrant@fixture.hashing.q.p"
    assert result.hits
    assert grounding.policy.threshold(result.retriever) == RetrievalSettings().threshold_qdrant


def test_selects_the_hybrid_of_bm25_and_qdrant() -> None:
    policy, _ = shared_policy()
    grounding = build_grounding(RetrievalSettings(retriever="qdrant_hybrid"), policy.repository, vectors=vectors())
    result = grounding.retriever.search(card_query(Language.PT))
    assert str(result.retriever) == "retriever:hybrid@bm25-qdrant.fixture.hashing.q.p"
    assert grounding.policy.threshold(result.retriever) == 0.0


@pytest.mark.parametrize("retriever", ["qdrant", "qdrant_hybrid"])
def test_a_missing_collection_never_stops_startup_and_bm25_answers(retriever: RetrieverName) -> None:
    policy, _ = shared_policy()
    missing = vectors(built=False)
    grounding = build_grounding(RetrievalSettings(retriever=retriever), policy.repository, vectors=missing)
    result = grounding.retriever.search(card_query())
    assert str(result.retriever) == "retriever:bm25@1"
    assert result.hits
    assert isinstance(missing.telemetry, RecordingTelemetry)
    assert missing.telemetry.counters[FALLBACK_METRIC].total == 1


def test_a_qdrant_retriever_needs_its_store_and_url() -> None:
    _, grounding = shared_policy()
    with pytest.raises(RetrievalIndexError, match="vector store"):
        build_retriever(RetrievalSettings(retriever="qdrant"), grounding.index, None)
    with pytest.raises(RetrievalIndexError, match="RETRIEVAL_QDRANT_URL"):
        build_vector_retrieval(
            RetrievalSettings(retriever="qdrant"), embedder=HashingEmbedder(), telemetry=RecordingTelemetry()
        )
    built = build_vector_retrieval(
        RetrievalSettings(retriever="qdrant", qdrant_url="http://qdrant:6333"),
        embedder=HashingEmbedder(),
        telemetry=RecordingTelemetry(),
    )
    assert type(built.store).__name__ == "QdrantVectorStore"


class FakeProvider:
    """An ``EmbeddingBackend`` that records the texts it receives (fixture)."""

    def __init__(self) -> None:
        self.texts: list[str] = []

    @property
    def model_id(self) -> str:
        return f"{MODEL}|4"

    def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        self.texts.extend(texts)
        return EmbeddingBatch(vectors=tuple((3.0, 4.0, 0.0, 0.0) for _ in texts), input_tokens=5, model_id=MODEL)


def test_the_hosted_embedder_redacts_the_query_and_records_its_cost() -> None:
    provider, telemetry = FakeProvider(), RecordingTelemetry()
    embedder = build_hosted_embedder(
        RetrievalSettings(), LLMSettings(), clock=FixedClock(NOW), telemetry=telemetry, provider=provider
    )
    vector = embedder.embed_query("mi correo es ana@example.com y quiero bloquear la tarjeta")
    assert vector == pytest.approx((0.6, 0.8, 0.0, 0.0))
    assert "ana@example.com" not in provider.texts[0]
    assert "bloquear la tarjeta" in provider.texts[0]
    assert embedder.model_id == f"{MODEL}|4"
    (cost, attributes), *_ = telemetry.histograms[COST_METRIC].values
    assert cost > 0
    assert attributes["gen_ai.operation.name"] == "embeddings"


def test_the_default_hosted_model_is_text_embedding_3_small_at_512_dimensions() -> None:
    settings = RetrievalSettings()
    assert (settings.hosted_embedding_model, settings.hosted_embedding_dimensions) == (MODEL, 512)
    assert settings.retriever == "bm25"
    assert settings.qdrant_url == ""
