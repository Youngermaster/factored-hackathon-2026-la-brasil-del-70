"""``bank-ml risk``: train, evaluate, and promote the learned snapshot risk estimators (``logreg``, ``lgbm``)."""

from pathlib import Path
from typing import Annotated

import typer

from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_ml.common.paths import ARTIFACTS_DIR, DOCS_EVALUATION_DIR, GOLD_DIR, REGISTRY_DIR
from bank_ml.common.reports import generated_now, git_sha
from bank_ml.common.tracking import tracker_for
from bank_ml.risk.evaluation import EVALUATION_FILE, evaluate_all
from bank_ml.risk.promotion import promote_all
from bank_ml.risk.training import train

app = typer.Typer(
    help="The learned snapshot risk estimator (synthetic data; never a lending decision).",
    no_args_is_help=True,
    add_completion=False,
)

RegistryOption = Annotated[Path, typer.Option(help="Model registry root (WORKFLOW_MODEL_REGISTRY_DIR).")]
GoldOption = Annotated[Path, typer.Option(help="Gold Parquet directory (make pipeline DATA_SOURCE=s3).")]
TrackingOption = Annotated[str | None, typer.Option(help="MLflow URI; 'none' disables tracking.")]
ArtifactsOption = Annotated[Path, typer.Option(help="Where dataset cards, runs, and evaluations are written.")]


@app.command("train")
def train_command(
    registry_dir: RegistryOption = REGISTRY_DIR,
    gold_dir: GoldOption = GOLD_DIR,
    tracking_uri: TrackingOption = None,
    artifacts_dir: ArtifactsOption = ARTIFACTS_DIR,
) -> None:
    """Build the dataset, fit logistic regression and LightGBM, calibrate, attach intervals, register candidates."""
    dataset, refs = train(FilesystemModelStore(registry_dir), tracker_for(tracking_uri), gold_dir, artifacts_dir)
    typer.echo(f"dataset {dataset.card.content_hash[:12]}: {dict(dataset.card.rows_per_split)}")
    for ref in refs.values():
        typer.echo(f"registered {ref} as candidate")


@app.command("evaluate")
def evaluate_command(
    registry_dir: RegistryOption = REGISTRY_DIR,
    gold_dir: GoldOption = GOLD_DIR,
    tracking_uri: TrackingOption = None,
    alias: Annotated[str, typer.Option(help="Alias or version to evaluate.")] = "candidate",
    report: Annotated[bool, typer.Option(help="Rewrite docs/evaluation/risk-estimator.md.")] = True,
    artifacts_dir: ArtifactsOption = ARTIFACTS_DIR,
) -> None:
    """Score the baselines and the registered models once on test; slices, disparities, and the report."""
    output = DOCS_EVALUATION_DIR / "risk-estimator.md" if report else None
    store, tracker = FilesystemModelStore(registry_dir), tracker_for(tracking_uri)
    result = evaluate_all(store, tracker, alias=alias, gold_dir=gold_dir, report=output, artifacts=artifacts_dir)
    for name, model in result["models"].items():
        typer.echo(f"{name}: test ROC AUC {model['test']['roc_auc']['estimate']:.3f}")


@app.command("promote")
def promote_command(
    approved_by: Annotated[str, typer.Option(help="Who approves the promotion (recorded).")],
    registry_dir: RegistryOption = REGISTRY_DIR,
    artifacts_dir: ArtifactsOption = ARTIFACTS_DIR,
) -> None:
    """Move 'champion' to each candidate that beats every reference on test; record the decision either way."""
    store = FilesystemModelStore(registry_dir)
    decisions = promote_all(
        store,
        artifacts_dir / "evaluations" / EVALUATION_FILE,
        approved_by=approved_by,
        now=generated_now(),
        commit=git_sha(),
    )
    for kind, decision in decisions.items():
        verdict = "promoted" if decision.promote else "refused"
        typer.echo(f"risk_estimator:{kind}: {verdict} ({'; '.join(decision.reasons)})")
