"""Grounding services: the bound clause lookup, open retrieval for informational questions, and the verifier.

Built once at startup. The bound lookup resolves every state of every workflow, so a missing binding stops the
process. The retriever comes from ``RETRIEVAL_RETRIEVER``; a stored index must match the loaded pack.
"""

from dataclasses import dataclass
from pathlib import Path

from bank_agent.adapters.retrieval.bm25 import Bm25Retriever
from bank_agent.adapters.retrieval.dense import DenseRetriever
from bank_agent.adapters.retrieval.embedding import CachingEmbedder, Embedder, SentenceTransformerEmbedder
from bank_agent.adapters.retrieval.hybrid import FusionComponent, HybridRetriever
from bank_agent.adapters.retrieval.index_store import RetrievalIndex, build_index, load_index
from bank_agent.application.grounding.bound import BoundPolicyLookup
from bank_agent.application.grounding.retrieval import InformationalRetrieval, RetrievalPolicy
from bank_agent.application.grounding.verifier import GroundingVerifier
from bank_agent.bootstrap.settings import RetrievalSettings
from bank_agent.domain.errors import RetrievalIndexError
from bank_agent.ports.policy import PolicyRepository
from bank_agent.ports.retrieval import Retriever


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
    # Fused scores carry no absolute relevance; the hybrid retriever abstains through its component floors.
    return RetrievalPolicy({"bm25": settings.threshold_bm25, "dense": settings.threshold_dense, "hybrid": 0.0})


def build_retriever(settings: RetrievalSettings, index: RetrievalIndex, embedder: Embedder | None) -> Retriever:
    bm25 = Bm25Retriever(index.bm25)
    if settings.retriever == "bm25":
        return bm25
    if index.dense is None or embedder is None:
        raise RetrievalIndexError(f"retriever {settings.retriever} needs a dense index and an embedder")
    dense = DenseRetriever(index.dense, embedder)
    if settings.retriever == "dense":
        return dense
    components = (FusionComponent(bm25, settings.threshold_bm25), FusionComponent(dense, settings.threshold_dense))
    return HybridRetriever(components, k=settings.rrf_k)


def build_grounding(
    settings: RetrievalSettings, repository: PolicyRepository, *, embedder: Embedder | None = None
) -> GroundingServices:
    needs_dense = settings.retriever != "bm25"
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
    retriever = build_retriever(settings, index, dense_embedder)
    policy = retrieval_policy(settings)
    return GroundingServices(
        bound=BoundPolicyLookup(repository),
        verifier=GroundingVerifier(repository),
        index=index,
        retriever=retriever,
        policy=policy,
        informational=InformationalRetrieval(retriever, policy, k=settings.answer_k),
    )
