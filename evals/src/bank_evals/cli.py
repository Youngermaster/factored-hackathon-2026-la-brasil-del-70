"""Command-line entry point `bank-eval`."""

from pathlib import Path

import typer

from bank_agent.adapters.embeddings.gateway import GatewayEmbedder, RedactingEmbedder
from bank_agent.adapters.embeddings.recorded import RecordedEmbedder
from bank_agent.adapters.llm.redaction import Redactor
from bank_agent.adapters.retrieval.embedding import (
    DEFAULT_EMBEDDING_MODEL,
    CachingEmbedder,
    SentenceTransformerEmbedder,
    ml_extra_installed,
)
from bank_agent.adapters.retrieval.ranking import DEFAULT_RRF_K
from bank_agent.adapters.vector.qdrant import QdrantVectorStore
from bank_agent.bootstrap.settings import DEFAULT_EMBEDDING_CACHE_DIR, DEFAULT_MODEL_CACHE_DIR, DEFAULT_POLICY_DIR
from bank_agent.domain.errors import ConfigurationError, RetrievalBackendError
from bank_evals import DISTRIBUTION_NAME, __version__
from bank_evals.commands import judge as judge_commands
from bank_evals.commands import publish as publish_commands
from bank_evals.commands import run as run_commands
from bank_evals.commands import scenarios as scenario_commands
from bank_evals.meta import generated_now, git_sha
from bank_evals.retrieval.command import (
    DEFAULT_RECORDED_EMBEDDINGS,
    DEFAULT_REPORT,
    display_path,
    run_retrieval_evaluation,
)
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


EMBEDDINGS_OPTION = typer.Option(DEFAULT_RECORDED_EMBEDDINGS, help="The recorded hosted embeddings.")


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
    qdrant: bool | None = typer.Option(
        None, "--qdrant/--no-qdrant", help="Default: when the recorded hosted embeddings exist (or when recording)."
    ),
    embeddings: Path = EMBEDDINGS_OPTION,
    record_embeddings: bool = typer.Option(
        False,
        help="Embed what the recording lacks with the live hosted model and rewrite it (opt-in; needs the litellm "
        "extra, LLM_API_KEY_PRIMARY, and RETRIEVAL_EMBEDDING_API_BASE of the evaluation account).",
    ),
    qdrant_url: str = typer.Option("", help="Search a real Qdrant at this URL instead of the in-memory store."),
) -> None:
    """Compare BM25, dense, hybrid, Qdrant, and Qdrant hybrid retrieval on the relevance judgments; write the report."""
    # Stamp the report with the commit and time at start: loading a local model can take minutes, and edits made
    # meanwhile must not mark the run's inputs as dirty.
    started_at, commit = generated_now(), git_sha()
    use_dense = ml_extra_installed() if dense is None else dense
    use_qdrant = (record_embeddings or embeddings.is_file()) if qdrant is None else qdrant
    embedder = query_embedder = None
    note = None if use_dense else "the optional ml extra is not installed or --no-dense was given"
    vector_note = None if use_qdrant else "no recorded hosted embeddings, or --no-qdrant was given"
    recorded = vector_embedder = None
    try:
        if use_dense:
            raw = SentenceTransformerEmbedder(model, cache_dir=model_cache)
            embedder, query_embedder = CachingEmbedder(raw, embedding_cache), raw
        if use_qdrant:
            recorded = recording(embeddings) if record_embeddings else RecordedEmbedder.replay(embeddings)
            vector_embedder = RedactingEmbedder(recorded, redactor=Redactor())
        run = run_retrieval_evaluation(
            judgments_path=judgments,
            policy_dir=policy_dir,
            output=output,
            tracker=MlflowTracker(tracking_uri) if mlflow else NullTracker(),
            generated_at=started_at,
            git_sha=commit,
            embedder=embedder,
            query_embedder=query_embedder,
            embedder_kind="sentence-transformers" if use_dense else None,
            dense_note=note,
            rrf_k=rrf_k,
            vector_embedder=vector_embedder,
            vector_store=QdrantVectorStore(qdrant_url, timeout_seconds=30.0) if qdrant_url else None,
            vector_note=vector_note,
            recorded=recorded,
        )
        if record_embeddings and recorded is not None:
            recorded.save(recorded_at=generated_now(), source=RECORDING_SOURCE)
            typer.echo(f"recorded {recorded.misses} new embeddings into {display_path(embeddings)}")
    except (ConfigurationError, JudgmentsError, RetrievalBackendError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    for report in run.evaluation.reports:
        test = report.test
        typer.echo(
            f"{report.name}: threshold {report.threshold:.4f}, test recall@3 {test.recall_at_3 or 0:.2f}, "
            f"MRR {test.mrr or 0:.2f}, abstention recall {test.abstention_recall or 0:.2f}"
        )
    typer.echo(f"wrote {display_path(output)}" + (f"; MLflow run {run.run_id}" if run.run_id else ""))


RECORDING_SOURCE = "Azure OpenAI evaluation account through LiteLLM (bank-eval retrieval --record-embeddings)"


def recording(path: Path) -> RecordedEmbedder:
    """The recording, filled from the live hosted model with the gateway's protections (the evaluation account)."""
    from bank_agent.adapters.system.clock import SystemClock
    from bank_agent.adapters.telemetry.noop import NoopTelemetry
    from bank_agent.bootstrap.embeddings import build_embedding_backend
    from bank_agent.bootstrap.settings import load_settings

    settings = load_settings()
    backend = build_embedding_backend(settings.retrieval, settings.llm, clock=SystemClock(), telemetry=NoopTelemetry())
    inner = GatewayEmbedder(backend)
    return RecordedEmbedder(path, model_id=inner.model_id, inner=inner)


app.command("run")(run_commands.run)
app.command("report")(run_commands.report)
app.command("compare")(run_commands.compare)
app.command("publish")(publish_commands.publish)
app.command("estimate")(publish_commands.estimate)
app.command("judge")(judge_commands.judge_command)
app.add_typer(scenario_commands.app)
