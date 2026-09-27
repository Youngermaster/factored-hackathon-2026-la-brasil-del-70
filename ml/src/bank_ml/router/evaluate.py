"""Router metrics: overall, per intent, per slice (language, locale, workflow), workflow confusion, calibration, and
the coverage-risk curve, each with item and seed-group counts and 95% cluster bootstrap intervals over seed groups.

High-stakes intents lead to a write, a protective action, or a handoff; a miss there skips something the customer
needed (or, for ``card_unblock_request`` and ``card_replacement_request``, the human who must handle it), so their
recall is reported on its own next to macro-F1.
"""

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from bank_agent.domain.workflow import CROSS_WORKFLOW_INTENTS, Intent
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_ml.common.metrics import (
    Interval,
    class_scores,
    cluster_bootstrap,
    confusion,
    coverage_risk,
    encode,
    expected_calibration_error,
    macro_f1,
    reliability,
)
from bank_ml.router.augment import Item
from bank_ml.router.models import Predictions

HIGH_STAKES = (
    Intent.DISPUTE_NEW,
    Intent.CARD_BLOCK,
    Intent.CARD_UNBLOCK_REQUEST,
    Intent.CARD_REPLACEMENT_REQUEST,
    Intent.CREDIT_APPLICATION,
    Intent.HUMAN_REQUEST,
)
CLASSES = tuple(sorted(Intent, key=lambda intent: intent.value))
WORKFLOW_LABELS = ("account_inquiry", "card_support", "dispute", "credit", "shared", "out_of_scope")


def workflow_of(intent: Intent) -> str:
    for descriptor in WORKFLOW_CATALOG.descriptors:
        if intent in descriptor.intents:
            return descriptor.id.value
    if intent is Intent.UNSUPPORTED:
        return "out_of_scope"
    return "shared" if intent in CROSS_WORKFLOW_INTENTS else "out_of_scope"


def interval(value: Interval) -> dict[str, float]:
    return {"estimate": value.estimate, "low": value.low, "high": value.high}


class Scored:
    """One model's predictions on one set of items, with encoded arrays for fast bootstrapping."""

    def __init__(self, name: str, items: Sequence[Item], predictions: Predictions) -> None:
        self.name = name
        self.items = list(items)
        self.predictions = predictions
        self.truth = encode([item.intent for item in items], CLASSES)
        self.predicted = encode(predictions.intents, CLASSES)
        self.correct = self.truth == self.predicted
        self.groups = [item.group_id for item in items]
        self.workflow_truth = encode([workflow_of(item.intent) for item in items], WORKFLOW_LABELS)
        self.workflow_predicted = encode([workflow_of(intent) for intent in predictions.intents], WORKFLOW_LABELS)
        self.covered = ~predictions.below_threshold

    def boot(self, key: str, statistic: Callable[[np.ndarray], float], mask: np.ndarray | None = None) -> Interval:
        chosen = np.arange(len(self.items)) if mask is None else np.flatnonzero(mask)
        groups = [self.groups[i] for i in chosen]

        def on_subset(indices: np.ndarray) -> float:
            return statistic(chosen[indices])

        return cluster_bootstrap(groups, on_subset, name=f"{self.name}:{key}")

    def accuracy(self, mask: np.ndarray | None = None) -> Interval:
        return self.boot("accuracy", lambda idx: float(self.correct[idx].mean()), mask)

    def macro_f1(self, mask: np.ndarray | None = None) -> Interval:
        return self.boot("macro_f1", lambda idx: macro_f1(self.truth[idx], self.predicted[idx], len(CLASSES)), mask)


def _risk(scored: Scored, idx: np.ndarray) -> float:
    covered = scored.covered[idx]
    return float((~scored.correct[idx][covered]).mean()) if covered.any() else 0.0


def summary(scored: Scored) -> dict[str, Any]:
    workflow_correct = scored.workflow_truth == scored.workflow_predicted
    recalls = {}
    for intent in HIGH_STAKES:
        mask = np.array([item.intent is intent for item in scored.items])
        recalls[intent.value] = interval(
            scored.boot(f"recall:{intent.value}", lambda i: float(scored.correct[i].mean()), mask)
        )
    confidence = scored.predictions.confidence
    canonical = np.array([item.augmentation == "canonical" for item in scored.items])
    return {
        "items": len(scored.items),
        "seed_groups": len(set(scored.groups)),
        "accuracy": interval(scored.accuracy()),
        "macro_f1": interval(scored.macro_f1()),
        "workflow_accuracy": interval(scored.boot("workflow", lambda idx: float(workflow_correct[idx].mean()))),
        "coverage": interval(scored.boot("coverage", lambda idx: float(scored.covered[idx].mean()))),
        "risk_at_threshold": interval(scored.boot("risk", lambda idx: _risk(scored, idx))),
        "ece": expected_calibration_error(confidence, scored.correct),
        "high_stakes_recall": recalls,
        "high_stakes_recall_mean": float(np.mean([value["estimate"] for value in recalls.values()])),
        "canonical_accuracy": float(np.mean(scored.correct[canonical])) if canonical.any() else 0.0,
    }


def per_intent(scored: Scored) -> list[dict[str, Any]]:
    matrix = confusion(scored.truth, scored.predicted, len(CLASSES))
    scores = class_scores(matrix, np.bincount(scored.truth, minlength=len(CLASSES)))
    rows = []
    for position, intent in enumerate(CLASSES):
        groups = {item.group_id for item in scored.items if item.intent is intent}
        score = scores[position]
        rows.append(
            {
                "intent": intent.value,
                "workflow": workflow_of(intent),
                "precision": score.precision,
                "recall": score.recall,
                "f1": score.f1,
                "items": score.support,
                "seed_groups": len(groups),
                "high_stakes": intent in HIGH_STAKES,
            }
        )
    return rows


def slices(scored: Scored, key: Callable[[Item], str]) -> list[dict[str, Any]]:
    values = sorted({key(item) for item in scored.items})
    rows = []
    for value in values:
        mask = np.array([key(item) == value for item in scored.items])
        rows.append(
            {
                "slice": value,
                "items": int(mask.sum()),
                "seed_groups": len({item.group_id for item, m in zip(scored.items, mask, strict=True) if m}),
                "accuracy": interval(scored.accuracy(mask)),
                "macro_f1": interval(scored.macro_f1(mask)),
            }
        )
    return rows


def workflow_confusion(scored: Scored) -> list[list[int]]:
    matrix = confusion(scored.workflow_truth, scored.workflow_predicted, len(WORKFLOW_LABELS))
    return [[int(value) for value in row] for row in matrix]


def calibration(scored: Scored) -> dict[str, Any]:
    bins = reliability(scored.predictions.confidence, scored.correct)
    curve = coverage_risk(scored.predictions.confidence, scored.correct)
    sampled = []
    for target in np.linspace(0.1, 1.0, 10):
        point = min(curve, key=lambda p: abs(p[1] - target)) if curve else (0.0, 0.0, 0.0)
        sampled.append({"threshold": point[0], "coverage": point[1], "risk": point[2]})
    return {
        "reliability": [bin_.__dict__ for bin_ in bins],
        "coverage_risk": sampled,
    }


def evaluate(scored: Scored) -> dict[str, Any]:
    return {
        "summary": summary(scored),
        "per_intent": per_intent(scored),
        "by_language": slices(scored, lambda item: item.language),
        "by_locale": slices(scored, lambda item: item.locale),
        "by_workflow": slices(scored, lambda item: workflow_of(item.intent)),
        "by_augmentation": slices(scored, lambda item: item.augmentation),
        "workflow_confusion": workflow_confusion(scored),
        "calibration": calibration(scored),
    }


def errors(scored: Scored, limit: int = 20) -> list[dict[str, Any]]:
    """Misrouted canonical test seeds (team-authored synthetic text), most confident first."""
    rows = [
        {
            "text": item.text,
            "locale": item.locale,
            "truth": item.intent.value,
            "predicted": predicted.value,
            "confidence": float(confidence),
        }
        for item, predicted, confidence, ok in zip(
            scored.items, scored.predictions.intents, scored.predictions.confidence, scored.correct, strict=True
        )
        if not ok and item.augmentation == "canonical"
    ]
    return sorted(rows, key=lambda row: -float(row["confidence"]))[:limit]
