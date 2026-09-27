"""The risk estimator end to end on the synthetic gold fixture: the dataset and label, training, the test evaluation
and report, promotion with a recorded decision, serving through the ``bank_agent`` composition root, the policy cut
points, and reproducibility."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bank_agent.adapters.models.learned_risk import LearnedRiskEstimator
from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_agent.adapters.models.score_band_risk import ScoreBandRiskEstimator
from bank_agent.bootstrap.models import build_model_registry, build_risk_estimator
from bank_agent.bootstrap.settings import WorkflowSettings
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.eligibility import CreditRiskFeatures, RiskBand
from bank_agent.domain.errors import ModelArtifactNotFoundError
from bank_agent.domain.locale import Country
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent_builders import T0
from bank_ml.cli import app
from bank_ml.common.reports import generated_now
from bank_ml.common.tracking import NullTracker
from bank_ml.risk.dataset import build_dataset
from bank_ml.risk.evaluation import EVALUATION_FILE, evaluate_all
from bank_ml.risk.promotion import promote_all
from bank_ml.risk.slices import policy_cuts
from bank_ml.risk.training import train

MEMBERS = 4


def _settings(registry: Path, selection: str) -> WorkflowSettings:
    return WorkflowSettings(_env_file=None, model_registry_dir=registry, risk_estimator=selection)


def _features(count: int) -> CreditRiskFeatures:
    return CreditRiskFeatures(jurisdiction=Country.CO, product_type=CreditProductType.CREDIT_CARD,
                              requested_term_months=12, credit_score=700, tenure_months=24,
                              credit_product_count=count, utilization=Decimal("0.4"), max_days_past_due=0)  # fmt: skip


def test_the_dataset_labels_open_credit_products_and_keeps_customers_apart(risk_gold: Path) -> None:
    dataset = build_dataset(risk_gold)
    splits: dict[str, set[str]] = {}
    for row in dataset.rows:
        splits.setdefault(row.split, set()).add(row.customer_id)
        assert row.credit_product_count >= 1
    assert not splits["train"] & splits["test"]
    assert not splits["dev"] & (splits["train"] | splits["test"])
    rate = sum(row.label for row in dataset.rows) / len(dataset.rows)
    assert 0.1 < rate < 0.5, "a closed product 180 days past due must not make every customer positive"
    assert any("unknown value" in item for item in dataset.card.filters)
    assert set(dataset.card.rows_per_split) == {"train", "calibration", "selection", "test"}


def test_train_evaluate_promote_and_serve(risk_gold: Path, tmp_path: Path) -> None:
    registry, artifacts = tmp_path / "registry", tmp_path / "artifacts"
    store = FilesystemModelStore(registry)
    _, refs = train(store, NullTracker(), risk_gold, artifacts, members=MEMBERS)
    assert set(refs) == {"logreg", "lgbm"}
    for kind in refs:
        manifest = store.registry.resolve(f"risk_estimator:{kind}", "candidate").metadata
        choice = manifest["interval_choice"]
        assert isinstance(choice, dict)
        assert choice["chosen"] in {"bootstrap", "venn_abers"}
        assert manifest["cuts"] == list(policy_cuts())
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps({"learned": {"logreg": {"artifact": "x"}, "lgbm": {"artifact": "y"}}}))
    refused = promote_all(store, stale, approved_by="x", now=generated_now(), commit="t")
    assert all("run evaluate first" in d.reasons[0] for d in refused.values())
    report = tmp_path / "risk-estimator.md"
    result = evaluate_all(store, NullTracker(), gold_dir=risk_gold, report=report, artifacts=artifacts)
    assert set(result["models"]) == {"score_band@1", "score_band_reestimated", "logreg", "lgbm"}
    text = report.read_text(encoding="utf-8")
    assert "It is not a lending model" in text
    assert "not a fairness certification" in text
    assert "Cross-sectional" in text
    decisions = promote_all(store, artifacts / "evaluations" / EVALUATION_FILE, approved_by="test approver",
                            now=generated_now(), commit="test")  # fmt: skip
    for kind, decision in decisions.items():
        history = store.history(f"risk_estimator:{kind}")
        last = history[-1]
        assert last["approved_by"] == "test approver"
        assert last["decision"] == ("promoted" if decision.promote else "refused")
        assert last["split"] == "test"
    again = promote_all(store, artifacts / "evaluations" / EVALUATION_FILE, approved_by="x", now=generated_now(),
                        commit="test")  # fmt: skip
    for kind, decision in decisions.items():
        if decision.promote:
            assert again[kind].reasons == ("the candidate is already the champion",)
    served = build_risk_estimator(_settings(registry, "lgbm@candidate"), build_model_registry(registry),
                                  FixedClock(T0), SequentialIdGenerator())  # fmt: skip
    assert isinstance(served, LearnedRiskEstimator)
    estimate = served.estimate(_features(2))
    assert estimate.label_definition == "snapshot_dpd30_any_credit_product"
    assert estimate.interval_low <= estimate.probability <= estimate.interval_high
    assert served.estimate(_features(0)).band is RiskBand.UNKNOWN
    assert estimate.model.version == refs["lgbm"].split("@")[1]


def test_the_api_keeps_the_baseline_without_an_artifact(tmp_path: Path) -> None:
    served = build_risk_estimator(_settings(tmp_path, "logreg@champion"), build_model_registry(tmp_path),
                                  FixedClock(T0), SequentialIdGenerator())  # fmt: skip
    assert isinstance(served, ScoreBandRiskEstimator)


def test_bands_use_the_policy_pack_cut_points() -> None:
    assert policy_cuts() == (0.20, 0.35, 0.01)


def test_retraining_reproduces_artifacts_and_metrics(risk_gold: Path, tmp_path: Path) -> None:
    first_store, second_store = FilesystemModelStore(tmp_path / "a"), FilesystemModelStore(tmp_path / "b")
    _, first = train(first_store, NullTracker(), risk_gold, tmp_path / "art-a", members=MEMBERS)
    _, second = train(second_store, NullTracker(), risk_gold, tmp_path / "art-b", members=MEMBERS)
    assert first == second
    for kind in first:
        name = f"risk_estimator:{kind}"
        a = first_store.registry.resolve(name, "candidate").metadata["metrics"]
        b = second_store.registry.resolve(name, "candidate").metadata["metrics"]
        assert a == b


def test_evaluate_and_promote_refuse_without_candidates_or_evaluation(risk_gold: Path, tmp_path: Path) -> None:
    store = FilesystemModelStore(tmp_path / "registry")
    with pytest.raises(ModelArtifactNotFoundError, match="run bank-ml risk train"):
        evaluate_all(store, NullTracker(), gold_dir=risk_gold, report=None, artifacts=tmp_path)
    missing = promote_all(store, tmp_path / "none.json", approved_by="x", now=generated_now(), commit="t")
    assert all("run bank-ml risk evaluate" in d.reasons[0] for d in missing.values())
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps({"learned": {"logreg": {"artifact": "x"}, "lgbm": {"artifact": "y"}}}))
    no_candidate = promote_all(store, stale, approved_by="x", now=generated_now(), commit="t")
    assert all("no candidate" in d.reasons[0] for d in no_candidate.values())


def test_the_cli_trains_evaluates_and_promotes(risk_gold: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    common = ["--registry-dir", str(tmp_path / "registry"), "--artifacts-dir", str(tmp_path / "artifacts")]
    data = ["--gold-dir", str(risk_gold), "--tracking-uri", "none"]
    trained = runner.invoke(app, ["risk", "train", *common, *data])
    assert trained.exit_code == 0, trained.output
    assert "registered risk_estimator:lgbm@" in trained.output
    evaluated = runner.invoke(app, ["risk", "evaluate", *common, *data, "--no-report"])
    assert evaluated.exit_code == 0, evaluated.output
    assert "logreg: test ROC AUC" in evaluated.output
    promoted = runner.invoke(app, ["risk", "promote", "--approved-by", "cli test", *common])
    assert promoted.exit_code == 0, promoted.output
    assert "risk_estimator:logreg:" in promoted.output
