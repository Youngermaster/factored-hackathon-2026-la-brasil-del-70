"""Ranking helpers shared by the retrievers: deterministic ordering and reciprocal rank fusion."""

from collections.abc import Iterable, Sequence

from bank_agent.adapters.retrieval.corpus import ClauseDocument
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.intelligence import RetrievalHit

DEFAULT_RRF_K = 60
"""The constant from Cormack, Clarke, and Buettcher (2009); larger values flatten the rank contributions."""


def rank_hits(scored: Iterable[tuple[ClauseDocument, float]], k: int) -> tuple[RetrievalHit, ...]:
    """The best ``k`` documents by score, ties broken by clause key, as hits ranked 1, 2, 3, and so on."""
    ordered = sorted(scored, key=lambda item: (-item[1], item[0].key))[:k]
    return tuple(
        RetrievalHit(clause=document.ref, score=score, rank=rank) for rank, (document, score) in enumerate(ordered, 1)
    )


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[ClauseRef]], k: int = DEFAULT_RRF_K
) -> list[tuple[ClauseRef, float]]:
    """Fuse ranked lists: each item scores the sum of ``1 / (k + rank)`` over the lists that contain it.

    Ranks start at 1. The result is ordered by fused score, ties broken by clause id and version.
    """
    if k < 0:
        raise ValueError("the fusion constant k must not be negative")
    fused: dict[ClauseRef, float] = {}
    for ranking in rankings:
        for rank, ref in enumerate(ranking, 1):
            fused[ref] = fused.get(ref, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda item: (-item[1], item[0].clause_id, item[0].version))
