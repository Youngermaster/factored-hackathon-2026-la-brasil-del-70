"""``bank-eval retrieval``: evaluate, write the report, and log the run."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bank_agent.adapters.embeddings.recorded import RecordedEmbedder
from bank_agent.adapters.policy.filesystem import FilesystemPolicyRepository
from bank_agent.adapters.retrieval.embedding import Embedder
from bank_agent.adapters.retrieval.ranking import DEFAULT_RRF_K
from bank_agent.ports.vector_store import VectorStore
from bank_evals.meta import REPOSITORY_ROOT
from bank_evals.retrieval.evaluation import RetrievalEvaluation, evaluate
from bank_evals.retrieval.judgments import judgments_digest, load_judgments
from bank_evals.retrieval.report import extract_hand_written, render_report, tracking_metrics
from bank_evals.retrieval.tracking import ExperimentTracker

DEFAULT_REPORT = REPOSITORY_ROOT / "docs" / "evaluation" / "retrieval.md"
DEFAULT_RECORDED_EMBEDDINGS = (
    REPOSITORY_ROOT / "evals" / "data" / "retrieval_embeddings.text-embedding-3-small-512.v1.jsonl"
)
"""Hosted query and passage embeddings for the judgments and the pack, recorded on the evaluation account."""


@dataclass(frozen=True)
class EvaluationRun:
    evaluation: RetrievalEvaluation
    report: str
    run_id: str | None


def display_path(path: Path) -> str:
    """The path relative to the repository when it is inside it, so reports never show absolute paths."""
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return path.name


def run_retrieval_evaluation(
    *,
    judgments_path: Path,
    policy_dir: Path,
    output: Path,
    tracker: ExperimentTracker,
    generated_at: datetime,
    git_sha: str,
    embedder: Embedder | None = None,
    query_embedder: Embedder | None = None,
    embedder_kind: str | None = None,
    dense_note: str | None = None,
    rrf_k: int = DEFAULT_RRF_K,
    vector_embedder: Embedder | None = None,
    vector_store: VectorStore | None = None,
    vector_note: str | None = None,
    recorded: RecordedEmbedder | None = None,
) -> EvaluationRun:
    """``recorded`` is the recorded-embeddings file below ``vector_embedder``; the report names it."""
    judgments = load_judgments(judgments_path)
    evaluation = evaluate(
        FilesystemPolicyRepository.from_directory(policy_dir),
        judgments,
        embedder=embedder,
        query_embedder=query_embedder,
        embedder_kind=embedder_kind,
        dense_note=dense_note,
        rrf_k=rrf_k,
        vector_embedder=vector_embedder,
        vector_store=vector_store,
        vector_note=vector_note,
    )
    digest = judgments_digest(judgments_path)
    previous = output.read_text(encoding="utf-8") if output.is_file() else ""
    report = render_report(
        evaluation,
        generated_at=generated_at,
        git_sha=git_sha,
        judgments_file=display_path(judgments_path),
        digest=digest,
        embeddings_file=display_path(recorded.path) if recorded is not None else None,
        embeddings_recorded_at=recorded.recorded_at if recorded is not None else None,
        hand_written=extract_hand_written(previous),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    params: dict[str, str | int | float] = {
        "judgments_file": display_path(judgments_path),
        "judgments_digest": digest,
        "pack_version": evaluation.pack_version,
        "tokenizer": evaluation.tokenizer,
        "embedding_model": evaluation.embedding_model or "none",
        "vector_model": evaluation.vector_model or "none",
        "rrf_k": rrf_k,
        "queries": len(judgments),
    }
    tags = {"git_sha": git_sha, "review_status": ",".join(sorted(evaluation.review_status)), "phase": "07"}
    run_id = tracker.log_run(
        "retrieval-comparison", params, tracking_metrics(evaluation), tags, {"retrieval.md": report}
    )
    return EvaluationRun(evaluation, report, run_id)
