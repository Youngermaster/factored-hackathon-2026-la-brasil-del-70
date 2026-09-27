"""Run each retriever over the judgments, tune its abstention threshold on ``dev``, and measure ``test``.

Ranking metrics (recall@k, MRR, nDCG@5) use the ranked list before the threshold, over in-scope queries.
Abstention metrics apply the threshold tuned on the ``dev`` split, which maximizes balanced accuracy between
abstaining on out-of-scope queries and answering in-scope ones; ties go to the lowest threshold. The hybrid
retriever is not tuned: its components keep only hits at or above their tuned thresholds, and it abstains when
nothing survives fusion.
"""

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise

from bank_agent.domain.base import UntrustedText
from bank_agent.domain.intelligence import RetrievalQuery
from bank_agent.ports.retrieval import Retriever
from bank_evals.retrieval.judgments import Judgment
from bank_evals.retrieval.metrics import (
    abstention_precision_recall,
    balanced_accuracy,
    ndcg_at_k,
    percentile,
    recall_at_k,
    reciprocal_rank,
)

DEPTH = 10


@dataclass(frozen=True)
class QueryResult:
    judgment: Judgment
    ranked: tuple[str, ...]
    top_score: float | None
    latency_ms: float

    def abstains(self, threshold: float) -> bool:
        return self.top_score is None or self.top_score < threshold


@dataclass(frozen=True)
class SliceMetrics:
    name: str
    n_in_scope: int
    n_out_of_scope: int
    recall_at_1: float | None
    recall_at_3: float | None
    recall_at_5: float | None
    mrr: float | None
    ndcg_at_5: float | None
    abstention_precision: float | None
    abstention_recall: float | None
    false_abstention_rate: float | None
    """Share of in-scope queries the threshold wrongly turns into abstentions."""


@dataclass(frozen=True)
class RetrieverReport:
    name: str
    model: str
    threshold: float
    tuned: bool
    dev: SliceMetrics
    test: SliceMetrics
    slices: tuple[SliceMetrics, ...]
    latency_p50_ms: float
    latency_p95_ms: float
    latency_mean_ms: float


def run_queries(
    retriever: Retriever, judgments: Iterable[Judgment], *, clock: Callable[[], float] = time.perf_counter
) -> list[QueryResult]:
    results = []
    for judgment in judgments:
        query = RetrievalQuery(
            text=UntrustedText(judgment.query), language=judgment.language, jurisdiction=judgment.jurisdiction, k=DEPTH
        )
        started = clock()
        hits = retriever.search(query).hits
        elapsed = (clock() - started) * 1000.0
        ranked = tuple(hit.clause.clause_id for hit in hits)
        results.append(QueryResult(judgment, ranked, hits[0].score if hits else None, elapsed))
    return results


def tune_threshold(results: Sequence[QueryResult]) -> float:
    """The threshold, among midpoints between distinct top scores, with the best balanced accuracy on ``results``."""
    scores = sorted({r.top_score for r in results if r.top_score is not None})
    if not scores:
        return 0.0
    candidates = [scores[0] - 1.0, *((a + b) / 2 for a, b in pairwise(scores)), scores[-1] + 1.0]
    expected = [r.judgment.expected == "abstain" for r in results]

    def accuracy(threshold: float) -> float:
        return balanced_accuracy([r.abstains(threshold) for r in results], expected)

    best = max(accuracy(candidate) for candidate in candidates)
    return min(candidate for candidate in candidates if accuracy(candidate) == best)


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def slice_metrics(name: str, results: Sequence[QueryResult], threshold: float) -> SliceMetrics:
    in_scope = [r for r in results if r.judgment.expected == "answer"]
    abstained = [r.abstains(threshold) for r in results]
    precision, recall = abstention_precision_recall(abstained, [r.judgment.expected == "abstain" for r in results])
    if len(in_scope) == len(results):
        precision = recall = None  # no out-of-scope query: the false abstention rate says it all
    return SliceMetrics(
        name=name,
        n_in_scope=len(in_scope),
        n_out_of_scope=len(results) - len(in_scope),
        recall_at_1=_mean([recall_at_k(r.ranked, r.judgment.grades, 1) for r in in_scope]),
        recall_at_3=_mean([recall_at_k(r.ranked, r.judgment.grades, 3) for r in in_scope]),
        recall_at_5=_mean([recall_at_k(r.ranked, r.judgment.grades, 5) for r in in_scope]),
        mrr=_mean([reciprocal_rank(r.ranked, r.judgment.grades) for r in in_scope]),
        ndcg_at_5=_mean([ndcg_at_k(r.ranked, r.judgment.grades, 5) for r in in_scope]),
        abstention_precision=precision,
        abstention_recall=recall,
        false_abstention_rate=_mean([1.0 if r.abstains(threshold) else 0.0 for r in in_scope]),
    )


def _slices(results: Sequence[QueryResult], threshold: float) -> tuple[SliceMetrics, ...]:
    keys: list[tuple[str, Callable[[Judgment], str]]] = [
        ("workflow", lambda j: j.workflow),
        ("language", lambda j: j.language.value),
        ("jurisdiction", lambda j: j.jurisdiction.value),
        ("locale", lambda j: j.locale.value),
    ]
    slices = []
    for dimension, key in keys:
        for value in sorted({key(r.judgment) for r in results}):
            group = [r for r in results if key(r.judgment) == value]
            slices.append(slice_metrics(f"{dimension}={value}", group, threshold))
    return tuple(slices)


def evaluate_retriever(
    retriever: Retriever,
    judgments: Sequence[Judgment],
    *,
    threshold: float | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> RetrieverReport:
    results = run_queries(retriever, judgments, clock=clock)
    dev = [r for r in results if r.judgment.split == "dev"]
    test = [r for r in results if r.judgment.split == "test"]
    chosen = tune_threshold(dev) if threshold is None else threshold
    latencies = [r.latency_ms for r in results]
    model = getattr(retriever, "model", None)
    return RetrieverReport(
        name=model.name if model is not None else type(retriever).__name__,
        model=str(model) if model is not None else "unknown",
        threshold=chosen,
        tuned=threshold is None,
        dev=slice_metrics("dev", dev, chosen),
        test=slice_metrics("test", test, chosen),
        slices=_slices(test, chosen),
        latency_p50_ms=percentile(latencies, 0.5),
        latency_p95_ms=percentile(latencies, 0.95),
        latency_mean_ms=sum(latencies) / len(latencies),
    )
