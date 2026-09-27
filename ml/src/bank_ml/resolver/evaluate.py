"""Resolver metrics per query, with 95% bootstrap intervals that resample customers.

- ``top1`` and ``mrr``: over queries whose target is among the candidates (a target the resolver did not rank
  counts as rank none, reciprocal rank 0).
- ``coverage``: the share of queries auto-selected (a clear winner at the model's margin).
- ``wrong_rate``: auto-selected queries whose winner is not the target, over all queries (target-absent queries
  included: any auto-selection there is wrong); ``wrong_among_auto``: the same over auto-selected queries.
- ``correct_clarify``: among queries that are not auto-selected and have a target, the share whose target is in
  the three options the workflow shows.
- ``absent_false_auto``: among target-absent queries, the share that were auto-selected anyway.
"""

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from bank_ml.common.metrics import cluster_bootstrap
from bank_ml.resolver.dataset import Query
from bank_ml.resolver.models import ResolverModel
from bank_ml.router.evaluate import interval

OPTIONS = 3


class Outcomes:
    def __init__(self, name: str, queries: Sequence[Query], model: ResolverModel) -> None:
        self.name = name
        self.queries = list(queries)
        ranks, auto, wrong, in_options = [], [], [], []
        for query in queries:
            resolution = model.rank(query)
            ids: list[str] = [str(candidate.transaction_id) for candidate in resolution.ranked]
            rank = ids.index(query.target_id) + 1 if query.target_id in ids else 0
            ranks.append(rank)
            auto.append(resolution.clear_winner is not None)
            wrong.append(resolution.clear_winner is not None and resolution.clear_winner != query.target_id)
            in_options.append(0 < rank <= OPTIONS)
        self.rank = np.array(ranks)
        self.auto = np.array(auto, dtype=bool)
        self.wrong = np.array(wrong, dtype=bool)
        self.in_options = np.array(in_options, dtype=bool)
        self.present = np.array([q.target_id is not None for q in queries], dtype=bool)
        self.customers = [q.customer_id for q in queries]

    def boot(self, key: str, statistic: Callable[[np.ndarray], float], mask: np.ndarray) -> dict[str, float]:
        chosen = np.flatnonzero(mask)
        if len(chosen) == 0:
            return {"estimate": float("nan"), "low": float("nan"), "high": float("nan")}

        def on_subset(indices: np.ndarray) -> float:
            return statistic(chosen[indices])

        return interval(cluster_bootstrap([self.customers[i] for i in chosen], on_subset, name=f"{self.name}:{key}"))

    def summary(self, mask: np.ndarray | None = None) -> dict[str, Any]:
        base = np.ones(len(self.queries), dtype=bool) if mask is None else mask
        present = base & self.present
        clarified = present & ~self.auto
        absent = base & ~self.present

        def mean_of(values: np.ndarray) -> Callable[[np.ndarray], float]:
            return lambda idx: float(values[idx].mean()) if len(idx) else 0.0

        reciprocal = np.where(self.rank > 0, 1.0 / np.maximum(self.rank, 1), 0.0)
        auto_idx = base & self.auto
        return {
            "queries": int(base.sum()),
            "customers": len({self.customers[i] for i in np.flatnonzero(base)}),
            "top1": self.boot("top1", mean_of(self.rank == 1), present),
            "mrr": self.boot("mrr", mean_of(reciprocal), present),
            "coverage": self.boot("coverage", mean_of(self.auto), base),
            "wrong_rate": self.boot("wrong", mean_of(self.wrong), base),
            "wrong_among_auto": self.boot("wrong_auto", mean_of(self.wrong), auto_idx),
            "correct_clarify": self.boot("clarify", mean_of(self.in_options), clarified),
            "clarified": int(clarified.sum()),
            "absent": int(absent.sum()),
            "absent_false_auto": self.boot("absent", mean_of(self.auto), absent),
        }


def slices(outcomes: Outcomes, key: Callable[[Query], str]) -> list[dict[str, Any]]:
    values = sorted({key(query) for query in outcomes.queries})
    return [
        {"slice": value, **outcomes.summary(np.array([key(q) == value for q in outcomes.queries], dtype=bool))}
        for value in values
    ]


def candidate_bucket(query: Query) -> str:
    size = len(query.candidates)
    return "1" if size == 1 else "2-3" if size <= 3 else "4-6" if size <= 6 else "7+"


def evaluate(outcomes: Outcomes) -> dict[str, Any]:
    multi = np.array([len(q.candidates) >= 2 for q in outcomes.queries], dtype=bool)
    return {
        "all": outcomes.summary(),
        "two_or_more_candidates": outcomes.summary(multi),
        "by_language": slices(outcomes, lambda q: q.language),
        "by_country": slices(outcomes, lambda q: q.country.value),
        "by_candidates": slices(outcomes, candidate_bucket),
        "by_amount_clue": slices(outcomes, lambda q: q.clues["amount"]),
        "by_merchant_clue": slices(outcomes, lambda q: q.clues["merchant"]),
        "by_date_clue": slices(outcomes, lambda q: q.clues["date"]),
    }


def failures(outcomes: Outcomes, limit: int = 12) -> list[dict[str, Any]]:
    """Wrong auto-selections and missed targets (synthetic descriptions of synthetic organizer transactions)."""
    rows = []
    for position, query in enumerate(outcomes.queries):
        if outcomes.wrong[position] or (query.target_id is not None and outcomes.rank[position] != 1):
            rows.append(
                {
                    "text": query.text,
                    "use": query.use,
                    "candidates": len(query.candidates),
                    "target_present": query.target_id is not None,
                    "auto_selected_wrong": bool(outcomes.wrong[position]),
                    "target_rank": int(outcomes.rank[position]),
                }
            )
    return rows[:limit]
