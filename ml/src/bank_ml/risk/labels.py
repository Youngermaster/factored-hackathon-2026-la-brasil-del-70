"""The risk label: any open credit product 30 or more days past due (``snapshot_dpd30_any_credit_product``).

With one snapshot of products (this delivery), the outcome is observed at the feature snapshot itself, so the label
is cross-sectional: it measures a concurrent association, never a forecast. With two or more monthly snapshots the
same definition becomes forward-looking: features from snapshot t and the outcome from exactly t plus a documented
horizon, strictly after. ``build_labels`` enforces both modes, so a future delivery changes the configuration, not
the code.

A customer whose open credit products all have unknown days past due has no label; one with any unknown value is
excluded too, because the unknown product could hide a positive.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

LABEL_DEFINITION = "snapshot_dpd30_any_credit_product"
DPD_THRESHOLD = 30


@dataclass(frozen=True)
class Outcome:
    """What one customer's open credit products show at ``snapshot``."""

    snapshot: date
    worst_days_past_due: int | None
    unknown_products: int


@dataclass(frozen=True)
class LabelConfig:
    feature_snapshot: date
    horizon_days: int = 0
    """0: cross-sectional (one snapshot). Positive: forward-looking; the outcome snapshot is the feature snapshot
    plus this many days."""

    def __post_init__(self) -> None:
        if self.horizon_days < 0:
            raise ValueError("the label horizon cannot be negative")

    @property
    def outcome_snapshot(self) -> date:
        return self.feature_snapshot + timedelta(days=self.horizon_days)

    @property
    def forward_looking(self) -> bool:
        return self.horizon_days > 0


def label_of(outcome: Outcome) -> int | None:
    """1 when the worst known value reaches the threshold and nothing is unknown, 0 below it, ``None`` otherwise."""
    if outcome.unknown_products > 0 or outcome.worst_days_past_due is None:
        return None
    return int(outcome.worst_days_past_due >= DPD_THRESHOLD)


@dataclass(frozen=True)
class LabelCounts:
    labeled: int
    positives: int
    unknown: int
    partly_unknown: int


def build_labels(config: LabelConfig, outcomes: Mapping[str, Outcome]) -> tuple[dict[str, int], LabelCounts]:
    """Labels per customer, refusing any outcome that is not at the configured outcome snapshot.

    A cross-sectional configuration accepts only outcomes at the feature snapshot; a forward-looking one only
    outcomes at the feature snapshot plus the horizon, which is strictly later than the features.
    """
    labels: dict[str, int] = {}
    unknown = partly = 0
    for customer, outcome in outcomes.items():
        if outcome.snapshot != config.outcome_snapshot:
            raise ValueError(
                f"outcome for {customer} is dated {outcome.snapshot}, expected {config.outcome_snapshot} "
                f"({'forward-looking' if config.forward_looking else 'cross-sectional'} label)"
            )
        label = label_of(outcome)
        if label is None:
            unknown += outcome.worst_days_past_due is None
            partly += outcome.worst_days_past_due is not None
            continue
        labels[customer] = label
    positives = sum(labels.values())
    return labels, LabelCounts(len(labels), positives, unknown, partly)
