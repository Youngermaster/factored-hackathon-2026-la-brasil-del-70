"""Deterministic split assignment: by group hash, by a temporal cutoff with a gap, and by stratified seed groups.

- ``group_split``: each group (for example a customer id) lands in one split by a salted hash, so no group
  appears in two splits and adding groups never moves existing ones.
- ``temporal_split``: reference instants before the cutoff are ``before``, those inside the gap window after it are
  ``gap`` (dropped), and later ones are ``after``.
- ``customer_temporal_split`` combines both: train and dev need a train or dev customer before the cutoff; test
  needs a test customer after the cutoff plus the gap. Everything else is excluded (``None``).
- ``stratified_group_split``: within each stratum (for example intent by locale), groups are ordered by a salted
  hash and dealt into test, dev, and train by fixed proportions, so every stratum is represented in every split.
"""

from collections import defaultdict
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from bank_ml.common.hashing import salted_order, salted_unit

Split = Literal["train", "dev", "test"]
SPLITS: tuple[Split, ...] = ("train", "dev", "test")
DEFAULT_FRACTIONS: Mapping[Split, float] = {"train": 0.70, "dev": 0.15, "test": 0.15}


def group_split(key: str, salt: str, fractions: Mapping[Split, float] = DEFAULT_FRACTIONS) -> Split:
    """The split of ``key`` (a group id) under ``fractions`` (which must sum to 1)."""
    if abs(sum(fractions.values()) - 1.0) > 1e-9:
        raise ValueError("split fractions must sum to 1")
    position = salted_unit(salt, key)
    cumulative = 0.0
    for split in SPLITS:
        cumulative += fractions.get(split, 0.0)
        if position < cumulative:
            return split
    return "test"


@dataclass(frozen=True)
class TemporalConfig:
    cutoff: date
    gap_days: int = 30

    def __post_init__(self) -> None:
        if self.gap_days < 0:
            raise ValueError("the gap cannot be negative")


def temporal_split(instant: datetime | date, config: TemporalConfig) -> Literal["before", "gap", "after"]:
    day = instant.date() if isinstance(instant, datetime) else instant
    if day < config.cutoff:
        return "before"
    if day < config.cutoff + timedelta(days=config.gap_days):
        return "gap"
    return "after"


def customer_temporal_split(
    customer_id: str,
    instant: datetime | date,
    config: TemporalConfig,
    salt: str,
    fractions: Mapping[Split, float] = DEFAULT_FRACTIONS,
) -> Split | None:
    """Train and dev before the cutoff from their customers; test after cutoff plus gap from test customers."""
    split = group_split(customer_id, salt, fractions)
    period = temporal_split(instant, config)
    if split == "test":
        return "test" if period == "after" else None
    return split if period == "before" else None


def _counts(size: int, test_share: float, dev_share: float) -> tuple[int, int]:
    if size < 3:
        return (0, 0)
    return max(1, round(size * test_share)), max(1, round(size * dev_share))


def stratified_group_split(
    strata: Mapping[str, Hashable], salt: str, test_share: float = 0.25, dev_share: float = 0.125
) -> dict[str, Split]:
    """Assign every group in ``strata`` (group id -> stratum) to a split, stratum by stratum.

    A stratum of fewer than three groups goes entirely to train (it cannot be evaluated without leaving train
    empty); the dataset card reports such strata.
    """
    by_stratum: dict[Hashable, list[str]] = defaultdict(list)
    for group, stratum in strata.items():
        by_stratum[stratum].append(group)
    assignment: dict[str, Split] = {}
    for groups in by_stratum.values():
        ordered = sorted(groups, key=lambda group: salted_order(salt, group))
        n_test, n_dev = _counts(len(ordered), test_share, dev_share)
        for position, group in enumerate(ordered):
            assignment[group] = "test" if position < n_test else "dev" if position < n_test + n_dev else "train"
    return assignment


def overlap(assignments: Iterable[tuple[str, Split]]) -> set[str]:
    """Groups that appear in more than one split (the leakage guard expects an empty set)."""
    seen: dict[str, set[Split]] = defaultdict(set)
    for group, split in assignments:
        seen[group].add(split)
    return {group for group, splits in seen.items() if len(splits) > 1}
