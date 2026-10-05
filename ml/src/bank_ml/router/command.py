"""``bank-ml router``: train, evaluate, promote, paraphrase, the hosted model reference, and the validation sheet."""

import asyncio
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import typer

from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_agent.bootstrap.models import default_embedder
from bank_agent.bootstrap.settings import RetrievalSettings
from bank_ml.common.paths import DOCS_EVALUATION_DIR, REGISTRY_DIR
from bank_ml.common.promotion import Guard, PromotionRule, promote
from bank_ml.common.reports import generated_now, git_sha
from bank_ml.common.tracking import tracker_for
from bank_ml.router.dataset import build_dataset
from bank_ml.router.paraphrase import SPLIT_OF, Purpose, build_client, generate
from bank_ml.router.pipeline import EmbedderFactory, evaluate_all, export_validation, train
from bank_ml.router.zero_shot import CASSETTE_DIR, classify_items
from bank_ml.router.zero_shot_report import DEFAULT_MODELS, SPLITS, TFIDF_REFERENCE, write_benchmark

RULE = PromotionRule(
    primary="dev_macro_f1",
    guards=(Guard("dev_high_stakes_recall_mean", 0.02), Guard("dev_workflow_accuracy", 0.02)),
)
MODELS = ("tfidf", "embeddings")
app = typer.Typer(help="The learned intent router.", no_args_is_help=True, add_completion=False)

RegistryOption = Annotated[Path, typer.Option(help="Model registry root (WORKFLOW_MODEL_REGISTRY_DIR).")]
TrackingOption = Annotated[str | None, typer.Option(help="MLflow URI; 'none' disables tracking.")]


def _embedder(enabled: bool) -> EmbedderFactory:
    return default_embedder(RetrievalSettings()) if enabled else (lambda: None)


@app.command("train")
def train_command(
    registry_dir: RegistryOption = REGISTRY_DIR,
    tracking_uri: TrackingOption = None,
    embeddings: Annotated[bool, typer.Option(help="Train the embedding router when the ml extra exists.")] = True,
) -> None:
    """Build the dataset, fit the learned routers, register them, and point 'candidate' at them."""
    result = train(FilesystemModelStore(registry_dir), tracker_for(tracking_uri), _embedder(embeddings))
    typer.echo(f"dataset {result.dataset.content_hash[:12]}: {dict(result.dataset.card.rows_per_split)}")
    for name, ref in result.registered.items():
        typer.echo(f"registered {ref} as candidate ({name})")
    for name, reason in result.skipped.items():
        typer.echo(f"skipped {name}: {reason}")


@app.command("evaluate")
def evaluate_command(
    registry_dir: RegistryOption = REGISTRY_DIR,
    tracking_uri: TrackingOption = None,
    alias: Annotated[str, typer.Option(help="Alias or version to evaluate.")] = "candidate",
    report: Annotated[bool, typer.Option(help="Rewrite docs/evaluation/router.md.")] = True,
) -> None:
    """Score baselines and registered models on test; write the evaluation JSON and the report."""
    output = DOCS_EVALUATION_DIR / "router.md" if report else None
    store, tracker = FilesystemModelStore(registry_dir), tracker_for(tracking_uri)
    result = evaluate_all(store, tracker, _embedder(True), alias=alias, report=output)
    for name, model in result["models"].items():
        test = model["test"]
        typer.echo(f"{name}: accuracy {test['accuracy']['estimate']:.3f}, macro-F1 {test['macro_f1']['estimate']:.3f}")


@app.command("promote")
def promote_command(
    approved_by: Annotated[str, typer.Option(help="Who approves the promotion (recorded).")],
    registry_dir: RegistryOption = REGISTRY_DIR,
    model: Annotated[str, typer.Option(help="tfidf, embeddings, or all.")] = "all",
) -> None:
    """Move 'champion' to 'candidate' when it wins on dev macro-F1 within the guards; record the decision."""
    store = FilesystemModelStore(registry_dir)
    for short in MODELS if model == "all" else (model,):
        if store.alias(f"router:{short}", "candidate") is None:
            typer.echo(f"router:{short}: no candidate")
            continue
        decision = promote(
            store, f"router:{short}", RULE, approved_by=approved_by, now=generated_now(), commit=git_sha()
        )
        typer.echo(f"router:{short}: {'promoted' if decision.promote else 'refused'} ({'; '.join(decision.reasons)})")


@app.command("paraphrase")
def paraphrase_command(
    purpose: Annotated[str, typer.Option(help="train (paraphrase_router_seed) or eval (paraphrase_router_eval).")],
) -> None:
    """Generate paraphrases through the gateway (LLM_* settings; cassettes replay recorded calls)."""
    if purpose not in SPLIT_OF:
        raise typer.BadParameter("purpose must be train or eval")
    chosen: Purpose = "train" if purpose == "train" else "eval"
    dataset = build_dataset()
    split_of = {item.seed_id: item.split for item in dataset.items}
    seeds = [seed for seed in dataset.seeds if split_of.get(seed.seed_id) == SPLIT_OF[chosen]]
    result = asyncio.run(generate(build_client(), seeds, chosen))
    if result.stopped:
        typer.echo(f"stopped: {result.stopped}; nothing written and no cassette created")
        raise typer.Exit(code=1)
    typer.echo(f"wrote {result.written} paraphrases to {result.path} ({result.failed} seeds failed)")


@app.command("zero-shot")
def zero_shot_command(
    model: Annotated[list[str] | None, typer.Option(help="LiteLLM model id; repeat for several.")] = None,
    split: Annotated[list[str] | None, typer.Option(help="dev and/or test (both by default).")] = None,
    record: Annotated[
        bool, typer.Option(help="Call the provider for items without a cassette (LLM_API_BASE, LLM_API_KEY_PRIMARY).")
    ] = False,
    concurrency: Annotated[int, typer.Option(min=1, max=16, help="Calls in flight when recording.")] = 8,
    per_minute: Annotated[float | None, typer.Option(help="Cap on live calls started per minute.")] = None,
    budget_usd: Annotated[float, typer.Option(help="Daily cost cap of the recording gateway (USD).")] = 10.0,
    limit: Annotated[int | None, typer.Option(min=1, help="Only the first N items of each split.")] = None,
    cassette_dir: Annotated[Path, typer.Option(help="Cassette directory.")] = CASSETTE_DIR,
    registry_dir: RegistryOption = REGISTRY_DIR,
    tfidf: Annotated[str, typer.Option(help="router:tfidf version or alias for the cascade.")] = TFIDF_REFERENCE,
    report: Annotated[bool, typer.Option(help="Rewrite docs/evaluation/router-llm.md (needs every split).")] = True,
) -> None:
    """The hosted language model as a zero-shot router and behind the classical routers (classify_intent_fallback@1).

    Without --record every call replays a cassette, so the report regenerates offline without a key."""
    models = model or list(DEFAULT_MODELS)
    splits = split or list(SPLITS)
    if unknown := sorted(set(splits) - set(SPLITS)):
        raise typer.BadParameter(f"unknown split {unknown}; use dev or test")
    if record and len(models) != 1:
        raise typer.BadParameter("record one model at a time (its key and endpoint come from LLM_* variables)")
    dataset = build_dataset()
    if record:
        items = [item for name in splits for item in dataset.split(name)[:limit]]
        run = asyncio.run(
            classify_items(
                models[0],
                items,
                cassette_dir,
                record=True,
                concurrency=concurrency,
                per_minute=per_minute,
                budget_usd=Decimal(str(budget_usd)),
            )
        )
        failures = sum(prediction.failed for prediction in run.predictions)
        typer.echo(f"{models[0]}: {len(items)} items, {run.recorded} recorded now, {failures} failed")
    if not report:
        return
    if limit is not None or set(splits) != set(SPLITS):
        raise typer.BadParameter("the report needs every item of dev and test; drop --limit and --split")
    output = DOCS_EVALUATION_DIR / "router-llm.md"
    result = write_benchmark(dataset, models, FilesystemModelStore(registry_dir), tfidf, cassette_dir, output)
    for name, system in result["systems"].items():
        test = system["test"]
        typer.echo(
            f"{name}: accuracy {test['accuracy']['estimate']:.3f}, macro-F1 {test['macro_f1']['estimate']:.3f}, "
            f"cost per 1,000 {test['usage']['cost_usd_per_1000']} USD"
        )
    typer.echo(f"wrote {output}")


@app.command("export-validation")
def export_validation_command() -> None:
    """Write the 200-item blind validation sheet and its key (kept when any label exists)."""
    typer.echo(f"validation sheet: {export_validation()}")
