"""The router dataset: seed groups, a stratified group split, augmentation, and cross-split deduplication.

1. Seeds whose canonical texts are near-duplicates (``SEED_MERGE_THRESHOLD``) join one seed group, whatever their
   intents: a cross-intent pair is a minimal pair ("bloquear" against "desbloquear"), kept in one split so neither
   text leaks into the other's split; the card counts them.
2. Seed groups are split within each (intent, locale) stratum of their first seed: 2 test, 1 dev, 5 train of 8.
3. Each seed is augmented; every item inherits its seed group's split. Paraphrase items (``extra``) do too.
4. Dev items that are near-duplicates of a train item, and test items that are near-duplicates of a train or dev
   item (``CROSS_SPLIT_THRESHOLD``), are removed and counted.
5. Every intent needs at least ``MIN_TRAIN_GROUPS`` train seed groups; the router cannot serve a workflow-level
   label (the port returns an ``Intent``), so a short intent stops the build instead of being merged.
"""

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from bank_agent.domain.workflow import Intent
from bank_ml.common.cards import DatasetCard, label_distribution
from bank_ml.common.dedup import (
    CROSS_SPLIT_THRESHOLD,
    SEED_MERGE_THRESHOLD,
    cluster,
    cross_split_duplicates,
    near_duplicate_pairs,
)
from bank_ml.common.hashing import rows_digest
from bank_ml.common.splits import Split, stratified_group_split
from bank_ml.router.augment import Item, augment, fill
from bank_ml.router.corpus import CORPUS_DIR, CorpusError, Seed, load_lexicon, load_seeds

DATASET_NAME = "router"
DATASET_VERSION = "router-v1"
SPLIT_SALT = "router-split-v1"
MIN_TRAIN_GROUPS = 4


@dataclass(frozen=True)
class RouterDataset:
    items: Sequence[Item]
    seeds: Sequence[Seed]
    groups: dict[str, str]
    merged_pairs: Sequence[tuple[str, str, float]]
    removed: Sequence[tuple[str, str, float]]
    card: DatasetCard

    def split(self, name: str) -> list[Item]:
        return [item for item in self.items if item.split == name]

    @property
    def content_hash(self) -> str:
        return self.card.content_hash


Pairs = list[tuple[str, str, float]]


def _group_splits(seeds: Sequence[Seed], canonical: dict[str, str]) -> tuple[dict[str, str], dict[str, Split], Pairs]:
    pairs = near_duplicate_pairs(canonical, SEED_MERGE_THRESHOLD)
    by_id = {seed.seed_id: seed for seed in seeds}
    groups = cluster([seed.seed_id for seed in seeds], pairs)
    strata = {group: f"{by_id[group].intent.value}|{by_id[group].locale}" for group in set(groups.values())}
    return groups, stratified_group_split(strata, SPLIT_SALT), pairs


def _dedupe(items: list[Item]) -> tuple[list[Item], list[tuple[str, str, float]]]:
    train = {item.item_id: item.text for item in items if item.split == "train"}
    dev = {item.item_id: item.text for item in items if item.split == "dev"}
    test = {item.item_id: item.text for item in items if item.split == "test"}
    found = cross_split_duplicates(train, dev, CROSS_SPLIT_THRESHOLD)
    kept_dev = {key: text for key, text in dev.items() if key not in found}
    found.update(cross_split_duplicates({**train, **kept_dev}, test, CROSS_SPLIT_THRESHOLD))
    removed = [(key, match, score) for key, (match, score) in sorted(found.items())]
    return [item for item in items if item.item_id not in found], removed


def build_dataset(corpus_dir: Path = CORPUS_DIR, extra: Sequence[Item] = ()) -> RouterDataset:
    seeds = load_seeds(corpus_dir)
    lexicon = load_lexicon(corpus_dir)
    canonical = {seed.seed_id: fill(seed, lexicon, None) for seed in seeds}
    groups, assignment, pairs = _group_splits(seeds, canonical)
    items = [
        item.with_split(groups[seed.seed_id], assignment[groups[seed.seed_id]])
        for seed in seeds
        for item in augment(seed, lexicon)
    ]
    items += [item.with_split(groups[item.seed_id], assignment[groups[item.seed_id]]) for item in extra]
    items, removed = _dedupe(items)
    train_groups = Counter(intent for intent, group in {(i.intent, i.group_id) for i in items if i.split == "train"})
    short = [intent.value for intent in Intent if train_groups[intent] < MIN_TRAIN_GROUPS]
    if short:
        raise CorpusError(f"intents with fewer than {MIN_TRAIN_GROUPS} train seed groups: {', '.join(short)}")
    return RouterDataset(items, seeds, groups, pairs, removed, _card(items, seeds, pairs, removed))


def _card(items: Sequence[Item], seeds: Sequence[Seed], pairs: Pairs, removed: Pairs) -> DatasetCard:
    rows = [asdict(item) for item in items]
    by_id = {seed.seed_id: seed for seed in seeds}
    minimal = [f"{a} ~ {b}" for a, b, _ in pairs if by_id[a].intent is not by_id[b].intent]
    per_split = Counter(item.split for item in items)
    provenance = Counter("team_authored" if item.provenance == "team_authored" else item.augmentation for item in items)
    return DatasetCard(
        name=DATASET_NAME,
        version=DATASET_VERSION,
        description=(
            "Team-authored router seed utterances (es-MX, es-CO, es-AR, pt-BR) expanded by deterministic "
            "augmentation. Organizer transcripts carry no intent signal and are not used. pt-BR seeds await "
            "native review; no language-model paraphrase is included until a provider exists."
        ),
        sources=["ml/corpus/router/seeds/*.yaml (team_authored)", "ml/corpus/router/lexicon.yaml"],
        filters=[
            f"seeds merged into one group at Jaccard >= {SEED_MERGE_THRESHOLD} on character 4-gram shingles",
            f"dev and test items removed at Jaccard >= {CROSS_SPLIT_THRESHOLD} to a train (or dev) item",
        ],
        split_method=(
            f"stratified seed-group split per (intent, locale), salt {SPLIT_SALT}: 2 test, 1 dev, 5 train of 8; "
            "every augmentation stays with its seed group"
        ),
        rows_per_split={split: per_split[split] for split in ("train", "dev", "test")},
        label_distribution=label_distribution((item.split, item.intent.value) for item in items),
        content_hash=rows_digest(rows),
        provenance=dict(provenance),
        notes=[
            f"{len(seeds)} seeds, {len({item.group_id for item in items})} seed groups, "
            f"{len(pairs)} merged seed pairs, {len(removed)} cross-split near-duplicates removed",
            f"{len(minimal)} cross-intent minimal pairs kept in one group: {', '.join(minimal) or 'none'}",
        ],
    )


def write_dataset(dataset: RouterDataset, root: Path) -> Path:
    directory = root / DATASET_NAME / dataset.content_hash[:12]
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "items.jsonl").open("w", encoding="utf-8") as stream:
        for item in dataset.items:
            stream.write(json.dumps(asdict(item), ensure_ascii=False, sort_keys=True) + "\n")
    dataset.card.write(directory)
    return directory
