"""The Markdown report (``docs/evaluation/retrieval.md``) and the flat metrics logged to MLflow."""

from collections.abc import Iterable
from datetime import datetime

from bank_evals.retrieval.evaluation import RetrievalEvaluation
from bank_evals.retrieval.runner import RetrieverReport, SliceMetrics

_COLUMNS = (
    "| Retriever | Slice | In scope | Out of scope | R@1 | R@3 | R@5 | MRR | nDCG@5 | Abst. P | Abst. R | False abst. |"
)
_RULE = "|---|---|---|---|---|---|---|---|---|---|---|---|"
DIMENSIONS = (("workflow", "By workflow"), ("language", "By language"), ("jurisdiction", "By jurisdiction"))


def _f(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _row(report: RetrieverReport, metrics: SliceMetrics) -> str:
    cells = [
        report.name,
        metrics.name,
        str(metrics.n_in_scope),
        str(metrics.n_out_of_scope),
        _f(metrics.recall_at_1),
        _f(metrics.recall_at_3),
        _f(metrics.recall_at_5),
        _f(metrics.mrr),
        _f(metrics.ndcg_at_5),
        _f(metrics.abstention_precision),
        _f(metrics.abstention_recall),
        _f(metrics.false_abstention_rate),
    ]
    return "| " + " | ".join(cells) + " |"


def _table(rows: Iterable[str]) -> list[str]:
    return [_COLUMNS, _RULE, *rows, ""]


def render_report(
    evaluation: RetrievalEvaluation, *, generated_at: datetime, git_sha: str, judgments_file: str, digest: str
) -> str:
    counts = evaluation.judgment_counts
    review = ", ".join(f"{status}: {n}" for status, n in sorted(evaluation.review_status.items()))
    model = (
        f"`{evaluation.embedding_model.split('|', 1)[0]}` ({evaluation.embedder_kind}, with its query and passage"
        " prefixes)"
        if evaluation.embedding_model
        else f"not run: {evaluation.dense_note or 'no embedder'}"
    )
    lines = [
        "# Retrieval evaluation",
        "",
        f"Generated {generated_at.isoformat()} from commit `{git_sha}` by `make eval-retrieval`",
        "(`bank-eval retrieval`). Do not edit by hand. The labeling protocol is in",
        "[retrieval-labeling.md](retrieval-labeling.md); the retrieval design is in",
        "[grounding](../workflows/grounding.md).",
        "",
        "| Input | Value |",
        "|---|---|",
        f"| Judgments | `{judgments_file}` (SHA-256 prefix `{digest}`): {counts.get('dev', 0)} dev, "
        f"{counts.get('test', 0)} test |",
        f"| Label review status | {review} |",
        f"| Policy pack | `{evaluation.pack_version}`, {evaluation.document_count} documents (ELG clauses excluded) |",
        f"| Tokenizer | `{evaluation.tokenizer}` |",
        f"| Embedding model | {model} |",
        f"| Fusion | reciprocal rank fusion, k = {evaluation.rrf_k}, component floors = tuned thresholds |",
        "",
        "**Read these numbers with their sample sizes.** Every label is team-written and still pending human review,",
        "so the results are provisional. Each workflow has 12 in-scope test queries, so one query moves a",
        "per-workflow recall by about 0.08; per-language and per-jurisdiction cells are just as small. Ranking",
        "metrics use in-scope queries before the threshold; abstention metrics use the threshold tuned on the dev",
        "split (the hybrid retriever abstains when no component hit clears its floor). Latency is measured in",
        "process on one machine, per query, including the query embedding for dense and hybrid.",
        "",
        "## Summary",
        "",
        "| Retriever | Model | Threshold | Split | R@1 | R@3 | R@5 | MRR | nDCG@5 | Abst. P | Abst. R | "
        "False abst. | p50 ms | p95 ms |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for report in evaluation.reports:
        threshold = f"{report.threshold:.4f}" + (" (tuned on dev)" if report.tuned else " (floors)")
        for metrics in (report.test, report.dev):
            lines.append(
                f"| {report.name} | `{report.model}` | {threshold} | {metrics.name} | {_f(metrics.recall_at_1)} | "
                f"{_f(metrics.recall_at_3)} | {_f(metrics.recall_at_5)} | {_f(metrics.mrr)} | "
                f"{_f(metrics.ndcg_at_5)} | {_f(metrics.abstention_precision)} | {_f(metrics.abstention_recall)} | "
                f"{_f(metrics.false_abstention_rate)} | {report.latency_p50_ms:.2f} | {report.latency_p95_ms:.2f} |"
            )
    lines.append("")
    for dimension, title in DIMENSIONS:
        lines += [f"## {title} (test split)", ""]
        rows = (
            _row(report, metrics)
            for report in evaluation.reports
            for metrics in report.slices
            if metrics.name.startswith(f"{dimension}=")
        )
        lines += _table(rows)
    lines += [
        "## Sample sizes",
        "",
        "| Split and workflow | Queries |",
        "|---|---|",
        *(f"| {key} | {value} |" for key, value in counts.items() if "." in key),
        "",
    ]
    return "\n".join(lines)


def _metric_name(text: str) -> str:
    return text.replace("=", ".").replace("-", "_")


def tracking_metrics(evaluation: RetrievalEvaluation) -> dict[str, float]:
    """Flat metric names such as ``bm25.test.recall_at_1`` or ``dense.workflow.dispute.mrr``."""
    metrics: dict[str, float] = {}
    for report in evaluation.reports:
        metrics[f"{report.name}.threshold"] = report.threshold
        metrics[f"{report.name}.latency_p50_ms"] = report.latency_p50_ms
        metrics[f"{report.name}.latency_p95_ms"] = report.latency_p95_ms
        for slice_ in (report.dev, report.test, *report.slices):
            for field in (
                "recall_at_1",
                "recall_at_3",
                "recall_at_5",
                "mrr",
                "ndcg_at_5",
                "abstention_precision",
                "abstention_recall",
                "false_abstention_rate",
            ):
                value = getattr(slice_, field)
                if value is not None:
                    metrics[f"{report.name}.{_metric_name(slice_.name)}.{field}"] = float(value)
    return metrics
