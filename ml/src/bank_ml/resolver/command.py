"""``bank-ml resolver``: train, evaluate, and promote the learned transaction resolver."""

from pathlib import Path
from typing import Annotated

import typer

from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_ml.common.paths import DOCS_EVALUATION_DIR, GOLD_DIR, REGISTRY_DIR
from bank_ml.common.promotion import Guard, PromotionRule, promote
from bank_ml.common.reports import generated_now, git_sha
from bank_ml.common.tracking import tracker_for
from bank_ml.resolver.pipeline import evaluate_all, train

RULE = PromotionRule(
    primary="dev_top1",
    guards=(
        Guard("dev_wrong_rate", 0.01, higher_is_better=False),
        Guard("dev_absent_false_auto", 0.05, higher_is_better=False),
    ),
)
app = typer.Typer(help="The learned transaction resolver.", no_args_is_help=True, add_completion=False)

RegistryOption = Annotated[Path, typer.Option(help="Model registry root (WORKFLOW_MODEL_REGISTRY_DIR).")]
GoldOption = Annotated[Path, typer.Option(help="Gold Parquet directory (make pipeline DATA_SOURCE=s3).")]
TrackingOption = Annotated[str | None, typer.Option(help="MLflow URI; 'none' disables tracking.")]


@app.command("train")
def train_command(
    registry_dir: RegistryOption = REGISTRY_DIR, gold_dir: GoldOption = GOLD_DIR, tracking_uri: TrackingOption = None
) -> None:
    """Build the dataset from gold, fit the LightGBM ranker, register it, and point 'candidate' at it."""
    dataset, ref = train(FilesystemModelStore(registry_dir), tracker_for(tracking_uri), gold_dir)
    typer.echo(f"dataset {dataset.card.content_hash[:12]}: {dict(dataset.card.rows_per_split)}")
    typer.echo(f"registered {ref} as candidate")


@app.command("evaluate")
def evaluate_command(
    registry_dir: RegistryOption = REGISTRY_DIR,
    gold_dir: GoldOption = GOLD_DIR,
    tracking_uri: TrackingOption = None,
    alias: Annotated[str, typer.Option(help="Alias or version to evaluate.")] = "candidate",
    report: Annotated[bool, typer.Option(help="Rewrite docs/evaluation/resolver.md.")] = True,
) -> None:
    """Score the rule baseline and the registered ranker on test; silver labels; write the report."""
    output = DOCS_EVALUATION_DIR / "resolver.md" if report else None
    store, tracker = FilesystemModelStore(registry_dir), tracker_for(tracking_uri)
    result = evaluate_all(store, tracker, alias=alias, gold_dir=gold_dir, report=output)
    for name, model in result["models"].items():
        for use, values in model["test"].items():
            top1 = values["two_or_more_candidates"]["top1"]["estimate"]
            typer.echo(f"{name} {use}: top-1 {top1:.3f} (two or more candidates)")


@app.command("promote")
def promote_command(
    approved_by: Annotated[str, typer.Option(help="Who approves the promotion (recorded).")],
    registry_dir: RegistryOption = REGISTRY_DIR,
) -> None:
    """Move 'champion' to 'candidate' when it wins on dev top-1 within the guards; record the decision."""
    store = FilesystemModelStore(registry_dir)
    if store.alias("resolver:lgbm", "candidate") is None:
        typer.echo("resolver:lgbm: no candidate")
        return
    decision = promote(store, "resolver:lgbm", RULE, approved_by=approved_by, now=generated_now(), commit=git_sha())
    typer.echo(f"resolver:lgbm: {'promoted' if decision.promote else 'refused'} ({'; '.join(decision.reasons)})")
