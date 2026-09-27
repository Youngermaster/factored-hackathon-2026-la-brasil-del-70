"""The leakage guard, dataset cards, promotion decisions, and the tracker selection."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_ml.common.cards import DatasetCard, label_distribution
from bank_ml.common.leakage import (
    POST_OUTCOME_COLUMNS,
    LeakageError,
    assert_no_leakage,
    leaking,
    referenced_identifiers,
)
from bank_ml.common.promotion import Guard, PromotionRule, decide, floats, promote
from bank_ml.common.tracking import MlflowTracker, NullTracker, environment_tags, tracker_for

RULE = PromotionRule(primary="macro_f1", guards=(Guard("recall", 0.02), Guard("ece", 0.05, higher_is_better=False)))
ARTIFACT = {"format": "fixture", "weights": [1, 2, 3]}


def test_the_denylist_and_the_outcome_prefix_are_refused() -> None:
    assert leaking(["amount", "Resolution_Days", "outcome_status", "merchant_name"]) == [
        "Resolution_Days",
        "outcome_status",
    ]
    assert "sla_breached" in POST_OUTCOME_COLUMNS
    with pytest.raises(LeakageError, match="was_resolved"):
        assert_no_leakage("fixture pipeline", ["amount", "was_resolved"])
    assert_no_leakage("fixture pipeline", ["amount"])
    assert referenced_identifiers('sql = "select claimed_amount, status from t"') >= {"claimed_amount", "status"}


def test_dataset_cards_render_json_and_markdown(tmp_path: Path) -> None:
    card = DatasetCard(
        name="fixture",
        version="1",
        description="A fixture card.",
        sources=["ml/corpus"],
        filters=["none"],
        split_method="seed groups",
        rows_per_split={"train": 2, "test": 1},
        label_distribution=label_distribution([("train", "a"), ("train", "b"), ("test", "a"), ("extra", "a")]),
        content_hash="0" * 64,
        provenance={"team_authored": 3},
        notes=["fixture only"],
    )
    card.write(tmp_path)
    assert '"content_hash"' in (tmp_path / "card.json").read_text()
    markdown = (tmp_path / "card.md").read_text()
    assert "| a | 1 | 1 | 1 |" in markdown
    assert "team_authored" in markdown
    assert list(card.label_distribution) == ["train", "test", "extra"]


def test_promotion_needs_a_better_primary_metric_within_every_guard() -> None:
    reference = {"macro_f1": 0.80, "recall": 0.90, "ece": 0.05}
    assert decide({"macro_f1": 0.85, "recall": 0.89, "ece": 0.08}, reference, RULE).promote
    assert not decide({"macro_f1": 0.85, "recall": 0.80, "ece": 0.05}, reference, RULE).promote
    assert not decide({"macro_f1": 0.85, "recall": 0.90, "ece": 0.20}, reference, RULE).promote
    assert not decide({"macro_f1": 0.80, "recall": 0.95, "ece": 0.01}, reference, RULE).promote
    missing = decide({"macro_f1": 0.9}, reference, RULE)
    assert not missing.promote
    assert "missing" in missing.reasons[0]
    assert floats({"a": 1, "b": True, "c": "x", "d": 0.5}) == {"a": 1.0, "d": 0.5}
    assert floats([1]) == {}


def test_promote_moves_the_champion_and_records_refusals(tmp_path: Path) -> None:
    store = FilesystemModelStore(tmp_path)
    now = datetime(2026, 9, 27, tzinfo=UTC)
    assert not promote(store, "router:tfidf", RULE, approved_by="x", now=now, commit="abc").promote
    metrics = {"macro_f1": 0.9, "recall": 0.9, "ece": 0.04}
    baseline = {**metrics, "macro_f1": 0.5}
    first = store.register("router:tfidf", ARTIFACT, {"metrics": metrics, "baseline_metrics": baseline})
    store.set_alias("router:tfidf", "candidate", first.ref.version, {"by": "train"})
    decision = promote(store, "router:tfidf", RULE, approved_by="reviewer", now=now, commit="abc")
    assert decision.promote
    champion = store.alias("router:tfidf", "champion")
    assert champion is not None
    assert champion["approved_by"] == "reviewer"
    assert champion["compared_with"] == "baseline"
    assert not promote(store, "router:tfidf", RULE, approved_by="reviewer", now=now, commit="abc").promote
    worse = store.register("router:tfidf", {**ARTIFACT, "weights": [0]}, {"metrics": {**metrics, "macro_f1": 0.7}})
    store.set_alias("router:tfidf", "candidate", worse.ref.version, {"by": "train"})
    assert not promote(store, "router:tfidf", RULE, approved_by="reviewer", now=now, commit="abc").promote
    assert store.registry.resolve("router:tfidf", "champion").ref == first.ref
    assert store.history("router:tfidf")[-1]["decision"] == "refused"


def test_tracker_selection_and_environment_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BANK_ML_TRACKING_URI", raising=False)
    assert isinstance(tracker_for("none"), NullTracker)
    assert isinstance(tracker_for(None), MlflowTracker)
    monkeypatch.setenv("BANK_ML_TRACKING_URI", "none")
    assert isinstance(tracker_for(None), NullTracker)
    assert NullTracker().log_run("e", "r", {}, {}, {}, {}) is None
    tags = environment_tags()
    assert tags["version.bank-ml"] != "absent"
    assert "python" in tags
