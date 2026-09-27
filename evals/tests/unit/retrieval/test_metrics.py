"""Ranking and abstention metrics against hand-computed values."""

import math

import pytest

from bank_evals.retrieval.metrics import (
    abstention_precision_recall,
    balanced_accuracy,
    ndcg_at_k,
    percentile,
    recall_at_k,
    reciprocal_rank,
)

RANKED = ["DSP-MX-2", "DSP-MX-1", "INF-ALL-1", "CRD-ALL-1"]


def test_recall_at_k_counts_relevant_clauses_in_the_top_k() -> None:
    relevant = {"DSP-MX-1": 2, "INF-ALL-1": 1}
    assert recall_at_k(RANKED, relevant, 1) == 0.0
    assert recall_at_k(RANKED, relevant, 2) == 0.5
    assert recall_at_k(RANKED, relevant, 3) == 1.0
    with pytest.raises(ValueError, match="at least one relevant"):
        recall_at_k(RANKED, {}, 3)


def test_reciprocal_rank_uses_the_first_relevant_clause() -> None:
    assert reciprocal_rank(RANKED, {"INF-ALL-1": 1, "CRD-ALL-1": 2}) == pytest.approx(1 / 3)
    assert reciprocal_rank(RANKED, {"ACC-ALL-1": 2}) == 0.0


def test_ndcg_uses_graded_gains_and_log_discounts() -> None:
    grades = {"DSP-MX-1": 2, "INF-ALL-1": 1}
    dcg = 3 / math.log2(3) + 1 / math.log2(4)
    idcg = 3 / math.log2(2) + 1 / math.log2(3)
    assert ndcg_at_k(RANKED, grades, 5) == pytest.approx(dcg / idcg)
    assert ndcg_at_k(["DSP-MX-1", "INF-ALL-1"], grades, 5) == pytest.approx(1.0)
    with pytest.raises(ValueError, match="at least one graded"):
        ndcg_at_k(RANKED, {}, 5)


def test_abstention_precision_and_recall_treat_abstention_as_positive() -> None:
    abstained = [True, True, False, False]
    expected = [True, False, True, False]
    assert abstention_precision_recall(abstained, expected) == (0.5, 0.5)
    assert abstention_precision_recall([False], [False]) == (None, None)
    with pytest.raises(ValueError, match="one prediction per judgment"):
        abstention_precision_recall([True], [])


def test_balanced_accuracy_averages_both_classes() -> None:
    assert balanced_accuracy([True, False, False, False], [True, True, False, False]) == pytest.approx(0.75)
    assert balanced_accuracy([False, False], [False, False]) == 1.0
    assert balanced_accuracy([], []) == 0.0


def test_percentile_is_nearest_rank() -> None:
    assert percentile([5.0, 1.0, 3.0, 2.0, 4.0], 0.5) == 3.0
    assert percentile([5.0, 1.0, 3.0, 2.0, 4.0], 0.95) == 5.0
    assert percentile([7.0], 0.0) == 7.0
    with pytest.raises(ValueError, match="at least one value"):
        percentile([], 0.5)
