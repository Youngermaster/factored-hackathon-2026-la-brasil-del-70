"""Grounding services: the bound clause lookup, open retrieval for informational questions, and the verifier.

Built once at startup. The bound lookup resolves every state of every workflow, so a missing binding stops the
process. The retriever comes from ``RETRIEVAL_RETRIEVER``; a stored index must match the loaded pack. The Qdrant
retrievers (ADR 0047) never stop the process: when the store or the collection is unavailable at startup, a
warning is logged and every query is answered by BM25 until it is back.
"""

from dataclasses import dataclass
from pathlib import Path

import structlog

from bank_agent.adapters.retrieval.bm25 import Bm25Retriever
from bank_agent.adapters.retrieval.dense import DenseRetriever
from bank_agent.adapters.retrieval.embedding import CachingEmbedder, Embedder, SentenceTransformerEmbedder
from bank_agent.adapters.retrieval.fallback import FallbackRetriever
from bank_agent.adapters.retrieval.hybrid import FusionComponent, HybridRetriever
from bank_agent.adapters.retrieval.index_store import RetrievalIndex, build_index, load_index
from bank_agent.adapters.retrieval.vector_index import VectorClauseIndex, VectorRetriever, model_version
from bank_agent.adapters.vector.qdrant import QdrantVectorStore
from bank_agent.application.grounding.bound import BoundPolicyLookup
from bank_agent.application.grounding.retrieval import InformationalRetrieval, RetrievalPolicy
from bank_agent.application.grounding.verifier import GroundingVerifier
from bank_agent.bootstrap.settings import QDRANT_RETRIEVERS, RetrievalSettings
from bank_agent.domain.errors import RetrievalBackendError, RetrievalIndexError
from bank_agent.domain.intelligence import ModelComponent, ModelRef
from bank_agent.ports.policy import PolicyRepository
from bank_agent.ports.retrieval import Retriever
from bank_agent.ports.telemetry import Telemetry
from bank_agent.ports.vector_store import VectorStore

_log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class GroundingServices:
    bound: BoundPolicyLookup
    verifier: GroundingVerifier
    index: RetrievalIndex
    retriever: Retriever
    policy: RetrievalPolicy
    informational: InformationalRetrieval


def build_embedder(model_name: str, *, model_cache_dir: Path, embedding_cache_dir: Path) -> Embedder:
    """A sentence-transformers model with the disk cache (needs the optional ``ml`` extra)."""
    return CachingEmbedder(SentenceTransformerEmbedder(model_name, cache_dir=model_cache_dir), embedding_cache_dir)


def retrieval_policy(settings: RetrievalSettings) -> RetrievalPolicy:
    # Fused scores carry no absolute relevance; the hybrid retrievers abstain through their component floors.
    return RetrievalPolicy(
        {
            "bm25": settings.threshold_bm25,
            "dense": settings.threshold_dense,
            "qdrant": settings.threshold_qdrant,
            "hybrid": 0.0,
        }
    )


@dataclass(frozen=True)
class VectorRetrieval:
    """What the Qdrant retrievers need: the store and the hosted embedder (with its gateway protections)."""

    store: VectorStore
    embedder: Embedder
    telemetry: Telemetry


def build_vector_retriever(
    settings: RetrievalSettings, index: RetrievalIndex, bm25: Bm25Retriever, vectors: VectorRetrieval
) -> Retriever:
    """``qdrant`` or ``qdrant_hybrid``, each behind the BM25 fallback. Checks the collection once, without failing."""
    clauses = VectorClauseIndex(vectors.store, vectors.embedder, pack_version=index.manifest.pack_version)
    try:
        clauses.check(len(index.documents))
    except RetrievalBackendError as error:
        _log.warning("retrieval_vector_index_unavailable", collection=clauses.name, error=error.code)
    dense = VectorRetriever(vectors.store, vectors.embedder, collection=clauses.name)
    primary: Retriever = dense
    model = dense.model
    if settings.retriever == "qdrant_hybrid":
        components = (FusionComponent(bm25, settings.threshold_bm25), FusionComponent(dense, settings.threshold_qdrant))
        version = f"bm25-qdrant.{model_version(vectors.embedder.model_id)}"[:64]
        primary = HybridRetriever(components, k=settings.rrf_k, version=version)
        model = ModelRef(component=ModelComponent.RETRIEVER, name="hybrid", version=version)
    return FallbackRetriever(primary, bm25, telemetry=vectors.telemetry, model=model)


def build_retriever(
    settings: RetrievalSettings,
    index: RetrievalIndex,
    embedder: Embedder | None,
    vectors: VectorRetrieval | None = None,
) -> Retriever:
    bm25 = Bm25Retriever(index.bm25)
    if settings.retriever == "bm25":
        return bm25
    if settings.retriever in QDRANT_RETRIEVERS:
        if vectors is None:
            raise RetrievalIndexError(f"retriever {settings.retriever} needs a vector store and a hosted embedder")
        return build_vector_retriever(settings, index, bm25, vectors)
    if index.dense is None or embedder is None:
        raise RetrievalIndexError(f"retriever {settings.retriever} needs a dense index and an embedder")
    dense = DenseRetriever(index.dense, embedder)
    if settings.retriever == "dense":
        return dense
    components = (FusionComponent(bm25, settings.threshold_bm25), FusionComponent(dense, settings.threshold_dense))
    return HybridRetriever(components, k=settings.rrf_k)


def build_vector_retrieval(
    settings: RetrievalSettings, *, embedder: Embedder, telemetry: Telemetry, store: VectorStore | None = None
) -> VectorRetrieval:
    """The Qdrant store at ``RETRIEVAL_QDRANT_URL`` (unless one is injected) with the hosted embedder."""
    if store is None:
        if not settings.qdrant_url:
            raise RetrievalIndexError(f"retriever {settings.retriever} needs RETRIEVAL_QDRANT_URL")
        store = QdrantVectorStore(settings.qdrant_url, timeout_seconds=settings.qdrant_timeout_seconds)
    return VectorRetrieval(store=store, embedder=embedder, telemetry=telemetry)


def build_grounding(
    settings: RetrievalSettings,
    repository: PolicyRepository,
    *,
    embedder: Embedder | None = None,
    vectors: VectorRetrieval | None = None,
) -> GroundingServices:
    needs_dense = settings.retriever in {"dense", "hybrid"}
    if needs_dense and embedder is None:
        embedder = build_embedder(
            settings.embedding_model,
            model_cache_dir=settings.model_cache_dir,
            embedding_cache_dir=settings.embedding_cache_dir,
        )
    dense_embedder = embedder if needs_dense else None
    if settings.index_source == "stored":
        model_id = dense_embedder.model_id if dense_embedder is not None else None
        index = load_index(settings.index_dir, repository, embedding_model=model_id)
    else:
        index = build_index(repository, embedder=dense_embedder)
    retriever = build_retriever(settings, index, dense_embedder, vectors)
    policy = retrieval_policy(settings)
    return GroundingServices(
        bound=BoundPolicyLookup(repository),
        verifier=GroundingVerifier(repository),
        index=index,
        retriever=retriever,
        policy=policy,
        informational=InformationalRetrieval(retriever, policy, k=settings.answer_k),
    )
