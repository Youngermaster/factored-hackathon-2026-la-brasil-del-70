"""The Qdrant rows of the retrieval evaluation: the recorded hosted embeddings, the cross-language slices, the
pre-registered switching rule, and the hand-written section that survives regeneration. Offline: the vectors are
the committed recording or the hashing fixture, and the store is in memory."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from bank_agent.adapters.embeddings.gateway import RedactingEmbedder
from bank_agent.adapters.embeddings.recorded import RecordedEmbedder
from bank_agent.adapters.llm.redaction import Redactor
from bank_agent.adapters.policy.filesystem import FilesystemPolicyRepository
from bank_agent.adapters.retrieval.corpus import build_corpus
from bank_agent.bootstrap.settings import DEFAULT_POLICY_DIR
from bank_agent_retrieval import HashingEmbedder
from bank_evals.retrieval.command import DEFAULT_RECORDED_EMBEDDINGS
from bank_evals.retrieval.decision import decide
from bank_evals.retrieval.evaluation import RetrievalEvaluation, evaluate
from bank_evals.retrieval.judgments import DEFAULT_JUDGMENTS, load_judgments
from bank_evals.retrieval.report import (
    DEFAULT_HAND_WRITTEN,
    HAND_WRITTEN_END,
    HAND_WRITTEN_START,
    extract_hand_written,
    render_report,
)
from bank_evals.retrieval.runner import SliceMetrics


@pytest.fixture(scope="module")
def evaluation() -> RetrievalEvaluation:
    repository = FilesystemPolicyRepository.from_directory(DEFAULT_POLICY_DIR)
    return evaluate(repository, load_judgments(DEFAULT_JUDGMENTS), vector_embedder=HashingEmbedder())


def test_adds_qdrant_and_its_hybrid_after_bm25(evaluation: RetrievalEvaluation) -> None:
    assert [report.name for report in evaluation.reports] == ["bm25", "qdrant", "qdrant_hybrid"]
    assert evaluation.reports[1].model == "retriever:qdrant@fixture.hashing.q.p"
    assert evaluation.reports[2].model == "retriever:hybrid@bm25-qdrant.fixture.hashing.q.p"
    assert evaluation.vector_store == "InMemoryVectorStore"
    assert evaluation.reports[1].tuned is True
    assert evaluation.reports[2].threshold == 0.0


def test_reports_both_cross_language_directions_over_the_in_scope_test_queries(
    evaluation: RetrievalEvaluation,
) -> None:
    for report in evaluation.reports:
        cross = {item.name: item for item in report.slices if item.name.startswith("cross_language=")}
        assert set(cross) == {"cross_language=es_to_pt", "cross_language=pt_to_es"}
        assert (cross["cross_language=es_to_pt"].n_in_scope, cross["cross_language=pt_to_es"].n_in_scope) == (36, 12)
        assert all(item.n_out_of_scope == 0 for item in cross.values())


def _with_language_recall(
    evaluation: RetrievalEvaluation, name: str, language: str, recall: float
) -> RetrievalEvaluation:
    reports = []
    for report in evaluation.reports:
        changed = report
        if report.name == name:
            slices = tuple(
                replace(item, recall_at_1=recall) if item.name == f"language={language}" else item
                for item in report.slices
            )
            changed = replace(report, slices=slices)
        reports.append(changed)
    return replace(evaluation, reports=tuple(reports))


def test_the_rule_needs_a_higher_mrr_and_no_recall_loss_in_either_language(
    evaluation: RetrievalEvaluation,
) -> None:
    decision = decide(evaluation)
    assert decision is not None
    assert [check.name for check in decision.checks] == [
        "test MRR is higher",
        "es recall@1 is not lower",
        "es recall@3 is not lower",
        "es recall@5 is not lower",
        "pt recall@1 is not lower",
        "pt recall@3 is not lower",
        "pt recall@5 is not lower",
        "out-of-scope abstention recall is not lower",
    ]
    better = _with_language_recall(_with_language_recall(evaluation, "qdrant_hybrid", "pt", 1.0), "bm25", "pt", 0.0)
    worse = _with_language_recall(_with_language_recall(evaluation, "qdrant_hybrid", "pt", 0.0), "bm25", "pt", 1.0)
    pt_better = decide(better)
    pt_worse = decide(worse)
    assert pt_better is not None
    assert pt_worse is not None
    assert next(c for c in pt_better.checks if c.name == "pt recall@1 is not lower").passed is True
    assert next(c for c in pt_worse.checks if c.name == "pt recall@1 is not lower").passed is False
    assert pt_worse.switch is False


def test_without_the_candidate_there_is_no_decision(evaluation: RetrievalEvaluation) -> None:
    assert decide(replace(evaluation, reports=evaluation.reports[:1])) is None


def test_a_missing_metric_fails_its_check(evaluation: RetrievalEvaluation) -> None:
    hybrid = evaluation.reports[2]
    empty: SliceMetrics = replace(hybrid.test, mrr=None)
    decision = decide(replace(evaluation, reports=(*evaluation.reports[:2], replace(hybrid, test=empty))))
    assert decision is not None
    assert decision.checks[0].passed is False


def test_the_report_states_the_rule_outcome_and_keeps_the_hand_written_text(evaluation: RetrievalEvaluation) -> None:
    def render(hand_written: str | None) -> str:
        return render_report(
            evaluation,
            generated_at=datetime(2026, 10, 5, tzinfo=UTC),
            git_sha="abc1234",
            judgments_file="j.jsonl",
            digest="0" * 12,
            embeddings_file="e.jsonl",
            embeddings_recorded_at="2026-10-05T16:27:12+00:00",
            hand_written=hand_written,
        )

    first = render(None)
    assert "## Production decision (pre-registered rule)" in first
    assert "**Outcome: the rule" in first
    assert "## Cross-language (test split)" in first
    assert "`fixture/hashing` at q|p dimensions, from `e.jsonl`, recorded 2026-10-05T16:27:12+00:00" in first
    assert extract_hand_written(first) == DEFAULT_HAND_WRITTEN
    edited = first.replace(DEFAULT_HAND_WRITTEN, "We switch production after review.\n\nSecond paragraph.")
    kept = extract_hand_written(edited)
    assert kept == "We switch production after review.\n\nSecond paragraph."
    assert f"{HAND_WRITTEN_START}\n{kept}\n{HAND_WRITTEN_END}" in render(kept)
    assert extract_hand_written("no markers here") is None


def test_the_committed_recording_covers_the_current_pack_and_judgments() -> None:
    """Fails when the pack or the judgments change: re-record with `make eval-retrieval-embeddings`."""
    recorded = RecordedEmbedder.replay(DEFAULT_RECORDED_EMBEDDINGS)
    assert recorded.model_id == "azure/text-embedding-3-small|512"
    assert recorded.dimension == 512
    corpus = build_corpus(FilesystemPolicyRepository.from_directory(DEFAULT_POLICY_DIR))
    vectors = recorded.embed_passages([document.text for document in corpus])
    assert all(sum(value * value for value in vector) == pytest.approx(1.0, abs=1e-4) for vector in vectors)
    embedder = RedactingEmbedder(recorded, redactor=Redactor())
    for judgment in load_judgments(DEFAULT_JUDGMENTS):
        assert len(embedder.embed_query(judgment.query)) == 512
    assert recorded.misses == 0
