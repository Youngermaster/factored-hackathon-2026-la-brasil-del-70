"""The resolver end to end on the synthetic gold fixture: dataset, LightGBM training, the pure-Python tree
evaluator against LightGBM's own predictions, evaluation with silver labels, promotion, serving through the
``bank_agent`` composition root, and reproducibility."""

from datetime import date
from pathlib import Path

import numpy as np
import pytest

from bank_agent.adapters.models.lgbm_resolver import LgbmResolverArtifact, LgbmTransactionResolver
from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_agent.bootstrap.models import build_model_registry, build_resolver
from bank_agent.bootstrap.settings import WorkflowSettings
from bank_ml.common.promotion import promote
from bank_ml.common.reports import generated_now
from bank_ml.common.splits import TemporalConfig
from bank_ml.common.tracking import NullTracker
from bank_ml.resolver.command import RULE
from bank_ml.resolver.dataset import ResolverConfig, build_dataset
from bank_ml.resolver.models import UNFITTED, fit_lgbm, matrix
from bank_ml.resolver.pipeline import evaluate_all, train

CONFIG = ResolverConfig(
    temporal=TemporalConfig(cutoff=date(2026, 1, 1), gap_days=30),
    sizes={"train": 400, "dev": 120, "test": 120},
    sample_share=1.0,
)


def test_the_dataset_keeps_customers_and_periods_apart(synthetic_gold: Path) -> None:
    dataset = build_dataset(synthetic_gold, CONFIG)
    by_split: dict[str, set[str]] = {}
    for query in dataset.queries:
        by_split.setdefault(query.split, set()).add(query.customer_id)
        if query.split == "test":
            assert query.now.date() >= date(2026, 1, 31)
        else:
            assert query.now.date() < date(2026, 1, 1)
        if query.target_id is not None:
            assert query.target_id in {txn.transaction_id for txn in query.candidates}
        assert all(txn.customer_id == query.customer_id for txn in query.candidates)
    assert not by_split["train"] & by_split["test"]
    assert not by_split["dev"] & by_split["test"]
    assert all(q.target_id is not None for q in dataset.split("train"))
    assert {q.language for q in dataset.queries} == {"es", "pt"}


def test_the_served_trees_equal_lightgbm_predictions(synthetic_gold: Path) -> None:
    dataset = build_dataset(synthetic_gold, CONFIG)
    fitted = fit_lgbm(dataset.split("train"), dataset.split("dev"))
    resolver = LgbmTransactionResolver(LgbmResolverArtifact.model_validate(fitted.artifact), UNFITTED)
    features, _, _ = matrix(dataset.split("test"))
    ours = np.array(resolver.score_rows(features.tolist()))
    theirs = fitted.booster.predict(features, num_iteration=fitted.params["rounds"])
    assert np.abs(ours - theirs).max() < 1e-9


def test_train_evaluate_promote_and_serve(synthetic_gold: Path, tmp_path: Path) -> None:
    store = FilesystemModelStore(tmp_path / "registry")
    dataset, ref = train(store, NullTracker(), synthetic_gold, CONFIG, artifacts=tmp_path / "artifacts")
    report = tmp_path / "resolver.md"
    result = evaluate_all(
        store,
        NullTracker(),
        gold_dir=synthetic_gold,
        config=CONFIG,
        report=report,
        labeling_dir=tmp_path / "labeling",
        artifacts=tmp_path / "artifacts",
    )
    assert result["artifact"] == ref
    assert set(result["models"]) == {"rules@1", "lgbm"}
    assert set(result["models"]["lgbm"]["test"]) == {"dispute", "payment_lookup"}
    assert result["silver"]["counts"]["unique_match"] > 0
    assert result["silver"]["verification"]["status"] == "pending"
    assert (tmp_path / "labeling" / "resolver_silver_sample.csv").is_file()
    assert "## Silver labels (secondary)" in report.read_text()

    decision = promote(store, "resolver:lgbm", RULE, approved_by="integration test", now=generated_now(), commit="t")
    assert store.history("resolver:lgbm")[-1]["decision"] == ("promoted" if decision.promote else "refused")
    if not decision.promote:
        store.set_alias("resolver:lgbm", "champion", ref.split("@")[1], {"approved_by": "integration test"})
    settings = WorkflowSettings(_env_file=None, resolver="lgbm@champion", model_registry_dir=tmp_path / "registry")
    resolver = build_resolver(settings, build_model_registry(tmp_path / "registry"))
    assert isinstance(resolver, LgbmTransactionResolver)
    query = next(q for q in dataset.split("test") if q.target_id is not None)
    assert str(resolver.rank(query.descriptor, query.candidates, now=query.now).model) == ref


def test_retraining_reproduces_the_artifact(synthetic_gold: Path, tmp_path: Path) -> None:
    refs = [
        train(FilesystemModelStore(tmp_path / name), NullTracker(), synthetic_gold, CONFIG, artifacts=tmp_path / name)[
            1
        ]
        for name in ("first", "second")
    ]
    assert refs[0] == refs[1]


def test_evaluate_refuses_without_a_candidate(synthetic_gold: Path, tmp_path: Path) -> None:
    with pytest.raises(Exception, match="resolver train"):
        evaluate_all(FilesystemModelStore(tmp_path), NullTracker(), gold_dir=synthetic_gold, config=CONFIG, report=None)
