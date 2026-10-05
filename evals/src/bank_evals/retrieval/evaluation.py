"""Compare BM25, dense, hybrid, Qdrant, and Qdrant hybrid retrieval on the same judgments and the same corpus.

The Qdrant retrievers run over a ``VectorStore``: the in-memory store by default (exact cosine search, the same
ranking Qdrant returns for a collection this small, by the shared store contract) or a real Qdrant when one is given.
Their query and passage vectors come from the committed recorded embeddings, so the comparison runs offline.
"""

import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from bank_agent.adapters.retrieval.bm25 import Bm25Retriever
from bank_agent.adapters.retrieval.dense import DenseRetriever
from bank_agent.adapters.retrieval.embedding import Embedder
from bank_agent.adapters.retrieval.hybrid import FusionComponent, HybridRetriever
from bank_agent.adapters.retrieval.index_store import RetrievalIndex, build_index
from bank_agent.adapters.retrieval.ranking import DEFAULT_RRF_K
from bank_agent.adapters.retrieval.vector_index import VectorClauseIndex, VectorRetriever, model_version
from bank_agent.adapters.vector.memory import InMemoryVectorStore
from bank_agent.ports.policy import PolicyRepository
from bank_agent.ports.vector_store import VectorStore
from bank_evals.retrieval.judgments import Judgment, JudgmentsError
from bank_evals.retrieval.runner import RetrieverReport, evaluate_retriever


@dataclass(frozen=True)
class RetrievalEvaluation:
    reports: tuple[RetrieverReport, ...]
    pack_version: str
    tokenizer: str
    document_count: int
    embedding_model: str | None
    embedder_kind: str | None
    dense_note: str | None
    rrf_k: int
    vector_model: str | None = None
    vector_note: str | None = None
    vector_store: str | None = None
    judgment_counts: dict[str, int] = field(default_factory=dict)
    review_status: dict[str, int] = field(default_factory=dict)


def check_judgments_against_corpus(judgments: Sequence[Judgment], index: RetrievalIndex) -> None:
    """Every relevant clause must be a document the query can see (its language, its jurisdiction or ALL)."""
    for judgment in judgments:
        visible = {d.clause_id for d in index.documents if d.visible_to(judgment.language, judgment.jurisdiction)}
        missing = [item.clause_id for item in judgment.relevant if item.clause_id not in visible]
        if missing:
            raise JudgmentsError(f"{judgment.query_id} names clauses outside its corpus: {', '.join(missing)}")


def evaluate(
    repository: PolicyRepository,
    judgments: Sequence[Judgment],
    *,
    embedder: Embedder | None = None,
    query_embedder: Embedder | None = None,
    embedder_kind: str | None = None,
    dense_note: str | None = None,
    rrf_k: int = DEFAULT_RRF_K,
    vector_embedder: Embedder | None = None,
    vector_store: VectorStore | None = None,
    vector_note: str | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> RetrievalEvaluation:
    """Evaluate BM25 always, dense and hybrid when an embedder is given, and Qdrant and Qdrant hybrid when a
    vector embedder (the hosted model's recorded embeddings, behind query redaction) is given.

    ``query_embedder`` embeds the queries (default: ``embedder``); pass the uncached model so latency includes
    the query embedding.
    """
    index = build_index(repository, embedder=embedder)
    check_judgments_against_corpus(judgments, index)
    bm25 = Bm25Retriever(index.bm25)
    reports = [evaluate_retriever(bm25, judgments, clock=clock)]
    if index.dense is not None and embedder is not None:
        dense = DenseRetriever(index.dense, query_embedder or embedder)
        dense_report = evaluate_retriever(dense, judgments, clock=clock)
        hybrid = HybridRetriever(
            (FusionComponent(bm25, reports[0].threshold), FusionComponent(dense, dense_report.threshold)), k=rrf_k
        )
        reports += [dense_report, evaluate_retriever(hybrid, judgments, threshold=0.0, clock=clock)]
    store_kind = None
    if vector_embedder is not None:
        store = vector_store if vector_store is not None else InMemoryVectorStore()
        store_kind = type(store).__name__
        clauses = VectorClauseIndex(store, vector_embedder, pack_version=index.manifest.pack_version)
        clauses.build(index.documents)
        qdrant = VectorRetriever(store, vector_embedder, collection=clauses.name)
        qdrant_report = evaluate_retriever(qdrant, judgments, clock=clock)
        fused = HybridRetriever(
            (FusionComponent(bm25, reports[0].threshold), FusionComponent(qdrant, qdrant_report.threshold)),
            k=rrf_k,
            version=f"bm25-qdrant.{model_version(vector_embedder.model_id)}"[:64],
        )
        reports += [
            qdrant_report,
            evaluate_retriever(fused, judgments, threshold=0.0, name="qdrant_hybrid", clock=clock),
        ]
    counts = Counter(f"{j.split}.{j.workflow}" for j in judgments) + Counter(j.split for j in judgments)
    return RetrievalEvaluation(
        reports=tuple(reports),
        pack_version=index.manifest.pack_version,
        tokenizer=index.manifest.tokenizer,
        document_count=index.manifest.document_count,
        embedding_model=index.manifest.embedding_model,
        embedder_kind=embedder_kind if embedder is not None else None,
        dense_note=dense_note,
        rrf_k=rrf_k,
        vector_model=vector_embedder.model_id if vector_embedder is not None else None,
        vector_note=vector_note,
        vector_store=store_kind,
        judgment_counts=dict(sorted(counts.items())),
        review_status=dict(Counter(j.review_status for j in judgments)),
    )
