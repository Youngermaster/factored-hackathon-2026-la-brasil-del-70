"""Threshold tuning, slice metrics, latency, the Markdown report, and the tracking metrics, on a scripted retriever."""

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.intelligence import ModelComponent, ModelRef, RetrievalHit, RetrievalQuery, RetrievalResult
from bank_evals.retrieval.evaluation import RetrievalEvaluation
from bank_evals.retrieval.judgments import Judgment
from bank_evals.retrieval.report import render_report, tracking_metrics
from bank_evals.retrieval.runner import QueryResult, evaluate_retriever, slice_metrics, tune_threshold
from bank_evals.retrieval.tracking import NullTracker

MODEL = ModelRef(component=ModelComponent.RETRIEVER, name="scripted", version="1")


def judgment(query_id: str, *, split: str = "dev", relevant: str | None = "DSP-MX-1", language: str = "es") -> Judgment:
    fields: dict[str, Any] = {
        "query_id": query_id,
        "workflow": "dispute" if relevant else "out_of_scope",
        "query": f"fixture query {query_id}",
        "language": language,
        "locale": "es-MX" if language == "es" else "pt-BR",
        "jurisdiction": "MX",
        "relevant": [{"clause_id": relevant, "grade": 2}] if relevant else [],
        "expected": "answer" if relevant else "abstain",
        "split": split,
        "provenance": "team_generated",
        "review_status": "pending",
    }
    return Judgment.model_validate(fields)


class ScriptedRetriever:
    """Returns fixed hits per query text (fixture)."""

    model = MODEL

    def __init__(self, script: Mapping[str, list[tuple[str, float]]]) -> None:
        self._script = script

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        hits = tuple(
            RetrievalHit(clause=ClauseRef(clause_id=clause_id, version=1), score=score, rank=rank)
            for rank, (clause_id, score) in enumerate(self._script.get(query.text, []), 1)
        )
        return RetrievalResult(hits=hits, retriever=MODEL)


def result(j: Judgment, score: float | None, ranked: tuple[str, ...] = ("DSP-MX-1",)) -> QueryResult:
    return QueryResult(j, ranked if score is not None else (), score, 1.0)


def test_the_threshold_separates_in_scope_from_out_of_scope_on_dev() -> None:
    results = [
        result(judgment("dsp-01"), 6.0),
        result(judgment("dsp-02"), 4.0),
        result(judgment("oos-01", relevant=None), 2.0),
        result(judgment("oos-02", relevant=None), None),
    ]
    assert tune_threshold(results) == 3.0
    assert tune_threshold([result(judgment("oos-03", relevant=None), None)]) == 0.0


def test_ties_go_to_the_lowest_threshold() -> None:
    results = [result(judgment("dsp-01"), 5.0), result(judgment("dsp-02"), 3.0)]
    assert tune_threshold(results) == 2.0


def test_slice_metrics_without_out_of_scope_queries_report_false_abstentions_only() -> None:
    metrics = slice_metrics("workflow=dispute", [result(judgment("dsp-01"), 1.0)], threshold=2.0)
    assert (metrics.abstention_precision, metrics.abstention_recall, metrics.false_abstention_rate) == (None, None, 1.0)
    assert metrics.recall_at_1 == 1.0


def clock() -> Iterator[float]:
    value = 0.0
    while True:
        yield value
        value += 0.002


def test_evaluate_retriever_tunes_on_dev_and_reports_test_slices() -> None:
    judgments = [
        judgment("dsp-01"),
        judgment("oos-01", relevant=None),
        judgment("dsp-02", split="test", language="pt"),
        judgment("oos-02", split="test", relevant=None),
    ]
    script = {
        "fixture query dsp-01": [("DSP-MX-1", 5.0)],
        "fixture query oos-01": [("ACC-ALL-1", 1.0)],
        "fixture query dsp-02": [("INF-ALL-1", 4.0), ("DSP-MX-1", 3.5)],
        "fixture query oos-02": [("ACC-ALL-1", 0.5)],
    }
    ticks = clock()
    report = evaluate_retriever(ScriptedRetriever(script), judgments, clock=lambda: next(ticks))
    assert report.threshold == 3.0
    assert report.test.mrr == 0.5
    assert report.test.abstention_recall == 1.0
    assert report.latency_p50_ms == pytest.approx(2.0)
    assert [s.name for s in report.slices][:2] == ["workflow=dispute", "workflow=out_of_scope"]
    fixed = evaluate_retriever(ScriptedRetriever(script), judgments, threshold=0.0)
    assert fixed.tuned is False
    assert fixed.test.abstention_recall == 0.0

    evaluation = RetrievalEvaluation(
        reports=(report, fixed),
        pack_version="pack-fixture",
        tokenizer="fold-stop-trunc6@1",
        document_count=4,
        embedding_model=None,
        embedder_kind=None,
        dense_note="fixture run",
        rrf_k=60,
        judgment_counts={"dev": 2, "dev.dispute": 1, "test": 2},
        review_status={"pending": 4},
    )
    text = render_report(
        evaluation,
        generated_at=datetime(2026, 9, 27, tzinfo=UTC),
        git_sha="abc1234",
        judgments_file="j.jsonl",
        digest="0" * 12,
    )
    assert text.startswith("# Retrieval evaluation")
    assert "not run: fixture run" in text
    assert "| scripted | workflow=out_of_scope | 0 | 1 |" in text
    assert "| dev.dispute | 1 |" in text
    assert "3.0000 (tuned on dev)" in text
    assert "0.0000 (floors)" in text
    metrics = tracking_metrics(evaluation)
    assert metrics["scripted.threshold"] == 0.0
    assert metrics["scripted.test.mrr"] == 0.5
    assert "scripted.workflow.dispute.mrr" in metrics
    assert NullTracker().log_run("x", {}, metrics, {}, {}) is None
