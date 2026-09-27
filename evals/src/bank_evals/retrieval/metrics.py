"""Ranking and abstention metrics. Pure functions over clause ids; no retriever is involved here."""

import math
from collections.abc import Mapping, Sequence


def recall_at_k(ranked: Sequence[str], relevant: Mapping[str, int], k: int) -> float:
    """Share of the relevant clauses found in the top ``k``."""
    if not relevant:
        raise ValueError("recall needs at least one relevant clause")
    return len(set(ranked[:k]) & set(relevant)) / len(relevant)


def reciprocal_rank(ranked: Sequence[str], relevant: Mapping[str, int]) -> float:
    """``1 / rank`` of the first relevant clause, or 0 when none is ranked."""
    for rank, clause_id in enumerate(ranked, 1):
        if clause_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked: Sequence[str], grades: Mapping[str, int], k: int = 5) -> float:
    """Normalized discounted cumulative gain with gains ``2 ** grade - 1`` and ``log2(rank + 1)`` discounts."""
    if not grades:
        raise ValueError("nDCG needs at least one graded clause")

    def gain(grade: int, rank: int) -> float:
        return float(2**grade - 1) / math.log2(rank + 1)

    dcg = sum(gain(grades.get(clause_id, 0), rank) for rank, clause_id in enumerate(ranked[:k], 1))
    idcg = sum(gain(grade, rank) for rank, grade in enumerate(sorted(grades.values(), reverse=True)[:k], 1))
    return dcg / idcg


def abstention_precision_recall(
    abstained: Sequence[bool], expected: Sequence[bool]
) -> tuple[float | None, float | None]:
    """Precision and recall of abstention as the positive class; ``None`` when a denominator is zero."""
    if len(abstained) != len(expected):
        raise ValueError("one prediction per judgment")
    true_positive = sum(1 for got, want in zip(abstained, expected, strict=True) if got and want)
    predicted, actual = sum(abstained), sum(expected)
    precision = true_positive / predicted if predicted else None
    recall = true_positive / actual if actual else None
    return precision, recall


def balanced_accuracy(abstained: Sequence[bool], expected: Sequence[bool]) -> float:
    """Mean of the abstention rate on out-of-scope queries and the answer rate on in-scope queries."""
    rates = []
    for want in (True, False):
        group = [got for got, target in zip(abstained, expected, strict=True) if target is want]
        if group:
            rates.append(sum(1 for got in group if got is want) / len(group))
    return sum(rates) / len(rates) if rates else 0.0


def percentile(values: Sequence[float], share: float) -> float:
    """Nearest-rank percentile (``share`` in 0..1) of a non-empty sample."""
    if not values:
        raise ValueError("a percentile needs at least one value")
    ordered = sorted(values)
    rank = max(1, math.ceil(share * len(ordered)))
    return ordered[rank - 1]
