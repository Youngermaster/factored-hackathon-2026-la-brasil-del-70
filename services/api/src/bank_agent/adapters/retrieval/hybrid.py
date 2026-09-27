"""Hybrid retrieval: reciprocal rank fusion of BM25 and dense results.

Fused scores carry no absolute relevance (every top result scores about ``1 / (k + 1)``), so abstention cannot
use them. Each component keeps only its hits at or above its floor (the component's own abstention threshold)
before fusion; when nothing survives, the result is empty and the retrieval policy abstains.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from bank_agent.adapters.retrieval.ranking import DEFAULT_RRF_K, reciprocal_rank_fusion
from bank_agent.domain.intelligence import (
    ModelComponent,
    ModelRef,
    RetrievalHit,
    RetrievalQuery,
    RetrievalResult,
)
from bank_agent.ports.retrieval import Retriever

HYBRID_MODEL_NAME = "hybrid"
CANDIDATE_DEPTH = 20
"""How many hits each component contributes before fusion (the maximum ``RetrievalQuery.k``)."""


@dataclass(frozen=True)
class FusionComponent:
    retriever: Retriever
    floor: float


class HybridRetriever:
    def __init__(self, components: Sequence[FusionComponent], *, k: int = DEFAULT_RRF_K, version: str = "1") -> None:
        if not components:
            raise ValueError("hybrid retrieval needs at least one component")
        self._components = tuple(components)
        self.k = k
        self.model = ModelRef(component=ModelComponent.RETRIEVER, name=HYBRID_MODEL_NAME, version=version)

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        deep = query.model_copy(update={"k": CANDIDATE_DEPTH})
        rankings = []
        for component in self._components:
            hits = component.retriever.search(deep).hits
            rankings.append([hit.clause for hit in hits if hit.score >= component.floor])
        fused = reciprocal_rank_fusion(rankings, self.k)[: query.k]
        hits = tuple(RetrievalHit(clause=ref, score=score, rank=rank) for rank, (ref, score) in enumerate(fused, 1))
        return RetrievalResult(hits=hits, retriever=self.model)
