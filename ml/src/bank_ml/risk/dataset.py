"""The risk dataset: features, labels, splits, slices, and a dataset card.

Customers are split by salted hash (60% train, 20% dev, 20% test), so no customer is in two splits; there is no
temporal split because the delivery has one snapshot. Dev is halved by a second salted hash: ``calibration`` (early
stopping, calibrators, Venn-Abers counts) and ``selection`` (calibrator and interval choices, dev metrics). The
income band slice is the within-country income tertile with cut points from train customers only.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from bank_agent.adapters.models.risk_features import FEATURE_NAMES, vector
from bank_ml.common.cards import DatasetCard, label_distribution
from bank_ml.common.hashing import rows_digest, salted_unit
from bank_ml.common.splits import Split, group_split, overlap
from bank_ml.risk.gold import RiskGoldReader, SliceRow
from bank_ml.risk.labels import DPD_THRESHOLD, LABEL_DEFINITION, LabelConfig, build_labels

VERSION = "risk-v1"
SPLIT_SALT = "risk-split-v1"
DEV_SALT = "risk-dev-half-v1"
FRACTIONS: dict[Split, float] = {"train": 0.6, "dev": 0.2, "test": 0.2}


@dataclass(frozen=True)
class RiskRow:
    customer_id: str
    split: Split
    part: str
    """``calibration`` or ``selection`` for dev rows; the split name otherwise."""
    features: tuple[float, ...]
    label: int
    country: str
    segment: str
    income_band: str
    credit_product_count: int


@dataclass(frozen=True)
class Arrays:
    x: NDArray[np.float64]
    y: NDArray[np.int64]
    rows: tuple[RiskRow, ...]


@dataclass(frozen=True)
class RiskDataset:
    rows: tuple[RiskRow, ...]
    card: DatasetCard
    snapshot: date

    def arrays(self, *parts: str) -> Arrays:
        chosen = tuple(row for row in self.rows if row.part in parts or row.split in parts)
        x = np.array([row.features for row in chosen], dtype=np.float64).reshape(len(chosen), len(FEATURE_NAMES))
        return Arrays(x, np.array([row.label for row in chosen], dtype=np.int64), chosen)


def part_of(customer_id: str, split: Split) -> str:
    if split != "dev":
        return split
    return "calibration" if salted_unit(DEV_SALT, customer_id) < 0.5 else "selection"


def income_cuts(pairs: Sequence[tuple[str, Decimal | None]]) -> dict[str, tuple[float, float]]:
    """Tertile cut points of income per country from ``(country, income)`` pairs (train customers)."""
    by_country: dict[str, list[float]] = {}
    for country, income in pairs:
        if income is not None:
            by_country.setdefault(country, []).append(float(income))
    return {c: (float(np.quantile(v, 1 / 3)), float(np.quantile(v, 2 / 3))) for c, v in sorted(by_country.items())}


def income_band(country: str, income: Decimal | None, cuts: dict[str, tuple[float, float]]) -> str:
    if income is None or country not in cuts:
        return "missing"
    low, high = cuts[country]
    value = float(income)
    return "lower" if value <= low else "middle" if value <= high else "upper"


def build_dataset(gold_dir: Path) -> RiskDataset:
    reader = RiskGoldReader(gold_dir)
    try:
        features, outcomes, slices = reader.features(), reader.outcomes(), reader.slices()
    finally:
        reader.close()
    if not features:
        raise ValueError(f"no customer with an open credit product in {gold_dir}")
    snapshot = features[0].snapshot
    labels, counts = build_labels(LabelConfig(snapshot), outcomes)
    splits = {row.customer_id: group_split(row.customer_id, SPLIT_SALT, FRACTIONS) for row in features}
    if overlap(splits.items()):
        raise ValueError("a customer landed in two splits")
    unknown_slice = SliceRow("unknown", None, None)
    train_income = [
        (slices.get(r.customer_id, unknown_slice).country, slices.get(r.customer_id, unknown_slice).income)
        for r in features
        if splits[r.customer_id] == "train" and r.customer_id in labels
    ]
    cuts = income_cuts(train_income)
    rows: list[RiskRow] = []
    for feature in features:
        if feature.customer_id not in labels:
            continue
        info = slices.get(feature.customer_id, unknown_slice)
        split = splits[feature.customer_id]
        values = vector(feature.credit_score, feature.tenure_months, feature.credit_product_count, feature.utilization)
        rows.append(
            RiskRow(
                feature.customer_id,
                split,
                part_of(feature.customer_id, split),
                tuple(values),
                labels[feature.customer_id],
                info.country,
                info.segment or "missing",
                income_band(info.country, info.income, cuts),
                int(feature.credit_product_count or 0),
            )
        )
    digest = rows_digest(
        {"customer_id": r.customer_id, "split": r.split, "part": r.part, "features": r.features, "label": r.label}
        for r in rows
    )
    card = DatasetCard(
        name="risk",
        version=VERSION,
        description=(
            "Snapshot risk estimate dataset (synthetic organizer data; not a lending dataset). One row per customer "
            f"with an open credit product; label {LABEL_DEFINITION}: any open credit product {DPD_THRESHOLD} or more "
            "days past due at the single snapshot, so the label is cross-sectional, not a forecast."
        ),
        sources=[
            "gold credit_profiles_serving (features: " + ", ".join(FEATURE_NAMES) + ")",
            "gold products_serving (label: days past due of open credit products)",
            "gold customers_serving (slices only: country, segment)",
        ],
        filters=[
            "customers with at least one open credit product",
            f"excluded: {counts.unknown} customers with no known days past due on any open credit product",
            f"excluded: {counts.partly_unknown} customers with an unknown value on some open credit product",
            f"snapshot {snapshot}; no temporal split (one snapshot)",
        ],
        split_method="customer group split by salted hash 60/20/20; dev halved into calibration and selection",
        rows_per_split={s: sum(1 for r in rows if r.part == s) for s in ("train", "calibration", "selection", "test")},
        label_distribution=label_distribution((r.split, "positive" if r.label else "negative") for r in rows),
        content_hash=digest,
        notes=[
            "features exclude days past due (label), protected and proxy attributes, and identifiers",
            "segment, country, and income band are evaluation slices, never features",
        ],
        parameters={"income_cuts": {k: list(v) for k, v in cuts.items()}, "fractions": dict(FRACTIONS)},
    )
    return RiskDataset(tuple(rows), card, snapshot)
