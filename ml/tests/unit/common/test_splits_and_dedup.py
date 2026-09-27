"""Split determinism and isolation, the temporal gap, and the near-duplicate thresholds."""

from datetime import date, datetime

import pytest

from bank_ml.common.dedup import (
    CROSS_SPLIT_THRESHOLD,
    cluster,
    cross_split_duplicates,
    exact_cross_split_max,
    jaccard,
    near_duplicate_pairs,
    normalize_text,
    shingles,
)
from bank_ml.common.hashing import rows_digest, salted_unit
from bank_ml.common.seeds import rng, seed_for
from bank_ml.common.splits import (
    TemporalConfig,
    customer_temporal_split,
    group_split,
    overlap,
    stratified_group_split,
    temporal_split,
)

CONFIG = TemporalConfig(cutoff=date(2026, 1, 1), gap_days=30)


def test_seeds_and_hashes_are_stable_and_distinct() -> None:
    assert seed_for("a", 1) == seed_for("a", 1) != seed_for("a", 2)
    assert rng("x").random() == rng("x").random()
    assert 0.0 <= salted_unit("salt", "key") < 1.0
    assert rows_digest([{"b": 1, "a": 2}]) == rows_digest([{"a": 2, "b": 1}]) != rows_digest([{"a": 3}])


def test_group_split_is_deterministic_and_roughly_proportional() -> None:
    keys = [f"CUS-{index:05d}" for index in range(4000)]
    first = {key: group_split(key, "salt") for key in keys}
    assert first == {key: group_split(key, "salt") for key in reversed(keys)}
    shares = {split: sum(1 for value in first.values() if value == split) / len(keys) for split in ("train", "dev")}
    assert shares["train"] == pytest.approx(0.70, abs=0.03)
    assert shares["dev"] == pytest.approx(0.15, abs=0.03)
    assert {group_split(key, "other") for key in keys[:50]} != {first[key] for key in keys[:1]}
    with pytest.raises(ValueError, match="sum to 1"):
        group_split("x", "salt", {"train": 0.5})


def test_temporal_split_honours_the_gap() -> None:
    assert temporal_split(date(2025, 12, 31), CONFIG) == "before"
    assert temporal_split(datetime(2026, 1, 15, 12), CONFIG) == "gap"  # noqa: DTZ001
    assert temporal_split(date(2026, 1, 31), CONFIG) == "after"
    with pytest.raises(ValueError, match="negative"):
        TemporalConfig(cutoff=date(2026, 1, 1), gap_days=-1)


def test_customer_temporal_split_keeps_customers_and_periods_apart() -> None:
    customers = [f"CUS-{index:05d}" for index in range(600)]
    assigned = {
        (customer, day): customer_temporal_split(customer, day, CONFIG, "salt")
        for customer in customers
        for day in (date(2025, 6, 1), date(2026, 1, 10), date(2026, 3, 1))
    }
    for (_customer, day), split in assigned.items():
        if split == "test":
            assert day >= date(2026, 1, 31)
        elif split is not None:
            assert day < CONFIG.cutoff
        if day == date(2026, 1, 10):
            assert split is None
    assert overlap((customer, split) for (customer, _), split in assigned.items() if split is not None) == set()


def test_stratified_group_split_deals_every_stratum() -> None:
    strata = {f"{intent}:{index}": intent for intent in ("a", "b") for index in range(8)}
    strata["tiny:0"] = "tiny"
    assignment = stratified_group_split(strata, "salt")
    assert assignment == stratified_group_split(dict(reversed(list(strata.items()))), "salt")
    for intent in ("a", "b"):
        mine = [split for group, split in assignment.items() if group.startswith(intent)]
        counts = [mine.count("test"), mine.count("dev")]
        assert counts == [2, 1]
    assert assignment["tiny:0"] == "train"
    assert overlap([("g", "train"), ("g", "test"), ("h", "dev")]) == {"g"}


def test_normalization_and_shingles() -> None:
    assert normalize_text("¡Cartão  1234, BLOQUEADO!") == "cartao # bloqueado"
    assert shingles("ab") == frozenset({"ab"})
    assert jaccard(frozenset(), frozenset()) == 1.0
    assert jaccard(shingles("quiero bloquear mi tarjeta"), shingles("Quiero bloquear mi tarjeta!")) == 1.0


def test_near_duplicates_are_merged_above_the_threshold_only() -> None:
    texts = {
        "s1": "Quiero bloquear mi tarjeta ahora mismo",
        "s2": "quiero bloquear mi tarjeta ahora mismo por favor",
        "s3": "Cuál es el saldo de mi cuenta de ahorros",
    }
    pairs = near_duplicate_pairs(texts, 0.6)
    assert [(a, b) for a, b, _ in pairs] == [("s1", "s2")]
    assert near_duplicate_pairs(texts, 0.99) == []
    assert cluster(list(texts), pairs) == {"s1": "s1", "s2": "s1", "s3": "s3"}


def test_cross_split_duplicates_find_train_matches_and_agree_with_the_exact_scan() -> None:
    train = {"t1": "No reconozco un cargo de 500 pesos en Super Ahorro", "t2": "Quiero hablar con una persona"}
    test = {"x1": "no reconozco un cargo de 900 pesos en super ahorro", "x2": "Cuál es mi saldo disponible"}
    found = cross_split_duplicates(train, test, CROSS_SPLIT_THRESHOLD)
    assert set(found) == {"x1"}
    assert found["x1"][0] == "t1"
    remaining = [text for key, text in test.items() if key not in found]
    assert exact_cross_split_max(train.values(), remaining) < CROSS_SPLIT_THRESHOLD
