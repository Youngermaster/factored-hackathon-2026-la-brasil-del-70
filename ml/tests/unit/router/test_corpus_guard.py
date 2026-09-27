"""The leakage guard on the committed router corpus: no seed group in two splits, no duplicate or near-duplicate
text across splits, every intent and locale in every split, and a deterministic build."""

from collections import defaultdict
from itertools import combinations

import pytest

from bank_agent.domain.workflow import Intent
from bank_ml.common.dedup import CROSS_SPLIT_THRESHOLD, exact_cross_split_max, normalize_text
from bank_ml.router.corpus import LOCALES, load_seeds
from bank_ml.router.dataset import RouterDataset, build_dataset


@pytest.fixture(scope="module")
def dataset() -> RouterDataset:
    return build_dataset()


def test_no_seed_group_appears_in_two_splits(dataset: RouterDataset) -> None:
    splits: dict[str, set[str]] = defaultdict(set)
    for item in dataset.items:
        splits[item.group_id].add(item.split)
    assert all(len(found) == 1 for found in splits.values())
    assert all(dataset.groups[item.seed_id] == item.group_id for item in dataset.items)


def test_no_exact_duplicate_text_across_splits(dataset: RouterDataset) -> None:
    by_split = {name: {normalize_text(item.text) for item in dataset.split(name)} for name in ("train", "dev", "test")}
    for left, right in combinations(by_split, 2):
        assert not by_split[left] & by_split[right], (left, right)


def test_no_near_duplicate_text_across_splits_by_exact_scan(dataset: RouterDataset) -> None:
    train = [item.text for item in dataset.split("train")]
    dev = [item.text for item in dataset.split("dev")]
    test = [item.text for item in dataset.split("test")]
    assert exact_cross_split_max(train, dev) < CROSS_SPLIT_THRESHOLD
    assert exact_cross_split_max(train + dev, test) < CROSS_SPLIT_THRESHOLD


def test_every_intent_and_locale_is_in_every_split(dataset: RouterDataset) -> None:
    for name in ("train", "dev", "test"):
        cells = {(item.intent, item.locale) for item in dataset.split(name)}
        assert cells == {(intent, locale) for intent in Intent for locale in LOCALES}, name


def test_provenance_is_team_authored_or_names_its_seed(dataset: RouterDataset) -> None:
    for item in dataset.items:
        if item.augmentation == "canonical":
            assert item.provenance == "team_authored"
        else:
            assert item.provenance == f"augmented_from:{item.seed_id}"
    assert len(load_seeds()) == 17 * 4 * 8


def test_the_build_is_deterministic(dataset: RouterDataset) -> None:
    again = build_dataset()
    assert again.content_hash == dataset.content_hash
    assert dataset.card.rows_per_split == again.card.rows_per_split
