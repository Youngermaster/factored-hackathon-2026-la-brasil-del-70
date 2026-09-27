"""Command-line entry point `bank-eval`."""

from pathlib import Path

import typer

from bank_agent.adapters.retrieval.embedding import (
    DEFAULT_EMBEDDING_MODEL,
    CachingEmbedder,
    SentenceTransformerEmbedder,
    ml_extra_installed,
)
from bank_agent.adapters.retrieval.ranking import DEFAULT_RRF_K
from bank_agent.bootstrap.settings import DEFAULT_EMBEDDING_CACHE_DIR, DEFAULT_MODEL_CACHE_DIR, DEFAULT_POLICY_DIR
from bank_agent.domain.errors import ConfigurationError
from bank_evals import DISTRIBUTION_NAME, __version__
from bank_evals.meta import generated_now, git_sha
from bank_evals.retrieval.command import DEFAULT_REPORT, display_path, run_retrieval_evaluation
from bank_evals.retrieval.judgments import DEFAULT_JUDGMENTS, JudgmentsError
from bank_evals.retrieval.tracking import MlflowTracker, NullTracker

app = typer.Typer(
    name="bank-eval",
    help="Evaluation harness for the banking agent: scenarios, systems, graders, and reports.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Evaluation harness for the banking agent: scenarios, systems, graders, and reports."""


@app.command()
def version() -> None:
    """Print the distribution name and version."""
    typer.echo(f"{DISTRIBUTION_NAME} {__version__}")


@app.command()
def retrieval(
    judgments: Path = DEFAULT_JUDGMENTS,
    output: Path = DEFAULT_REPORT,
    policy_dir: Path = DEFAULT_POLICY_DIR,
    dense: bool | None = typer.Option(
        None, "--dense/--no-dense", help="Default: when the optional ml extra is installed."
    ),
    model: str = DEFAULT_EMBEDDING_MODEL,
    model_cache: Path = DEFAULT_MODEL_CACHE_DIR,
    embedding_cache: Path = DEFAULT_EMBEDDING_CACHE_DIR,
    rrf_k: int = DEFAULT_RRF_K,
    tracking_uri: str = typer.Option("file:./mlruns", envvar="MLFLOW_TRACKING_URI"),
    mlflow: bool = typer.Option(True, "--mlflow/--no-mlflow", help="Log the run to MLflow."),
) -> None:
    """Compare BM25, dense, and hybrid retrieval on the relevance judgments and write the report."""
    use_dense = ml_extra_installed() if dense is None else dense
    embedder = query_embedder = None
    note = None if use_dense else "the optional ml extra is not installed or --no-dense was given"
    try:
        if use_dense:
            raw = SentenceTransformerEmbedder(model, cache_dir=model_cache)
            embedder, query_embedder = CachingEmbedder(raw, embedding_cache), raw
        run = run_retrieval_evaluation(
            judgments_path=judgments,
            policy_dir=policy_dir,
            output=output,
            tracker=MlflowTracker(tracking_uri) if mlflow else NullTracker(),
            generated_at=generated_now(),
            git_sha=git_sha(),
            embedder=embedder,
            query_embedder=query_embedder,
            embedder_kind="sentence-transformers" if use_dense else None,
            dense_note=note,
            rrf_k=rrf_k,
        )
    except (ConfigurationError, JudgmentsError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    for report in run.evaluation.reports:
        test = report.test
        typer.echo(
            f"{report.name}: threshold {report.threshold:.4f}, test recall@3 {test.recall_at_3 or 0:.2f}, "
            f"MRR {test.mrr or 0:.2f}, abstention recall {test.abstention_recall or 0:.2f}"
        )
    typer.echo(f"wrote {display_path(output)}" + (f"; MLflow run {run.run_id}" if run.run_id else ""))
