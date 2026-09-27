"""The human validation sample for router labels: 200 test items stratified by intent and locale, a blind sheet,
a separate answer key, and the agreement and label accuracy once labels exist (``pending`` until then).

Protocol: ``docs/evaluation/router-labeling.md``. The sheet shows only the item id, locale, and text; the assigned
intent is in ``*.key.csv``, which labelers do not open. A rerun never overwrites a sheet that holds any label.
"""

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bank_ml.common.hashing import salted_order
from bank_ml.router.augment import Item
from bank_ml.router.corpus import CORPUS_DIR

SAMPLE_SIZE = 200
PER_CELL = 3
SALT = "router-validation-v1"
SHEET_COLUMNS = (
    "item_id",
    "locale",
    "text",
    "labeler_1_intent",
    "labeler_1_natural",
    "labeler_2_intent",
    "labeler_2_natural",
    "adjudicated_intent",
    "notes",
)
LABEL_COLUMNS = SHEET_COLUMNS[3:8]


@dataclass(frozen=True)
class ValidationFiles:
    sheet: Path
    key: Path

    @classmethod
    def default(cls, corpus_dir: Path = CORPUS_DIR) -> "ValidationFiles":
        base = corpus_dir / "validation"
        return cls(base / "router_validation_v1.csv", base / "router_validation_v1.key.csv")


def sample(test: list[Item]) -> list[Item]:
    """``PER_CELL`` items per (intent, locale) cell by salted order, then trimmed to ``SAMPLE_SIZE`` by removing at
    most one item from a cell (last in salted order first), so every cell keeps at least two items."""
    cells: dict[tuple[str, str], list[Item]] = defaultdict(list)
    for item in test:
        cells[(item.intent.value, item.locale)].append(item)
    chosen: dict[tuple[str, str], list[Item]] = {
        key: sorted(cells[key], key=lambda item: salted_order(SALT, item.item_id))[:PER_CELL] for key in sorted(cells)
    }
    excess = sum(len(items) for items in chosen.values()) - SAMPLE_SIZE
    for key in sorted(chosen, key=lambda cell: salted_order(SALT, "|".join(cell)), reverse=True):
        if excess <= 0:
            break
        if len(chosen[key]) > 2:
            chosen[key] = chosen[key][:-1]
            excess -= 1
    return sorted((item for items in chosen.values() for item in items), key=lambda item: item.item_id)


def _labeled(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open(encoding="utf-8") as stream:
        return any(any(row.get(column, "").strip() for column in LABEL_COLUMNS) for row in csv.DictReader(stream))


def export(test: list[Item], files: ValidationFiles) -> str:
    if _labeled(files.sheet):
        return "kept"
    items = sample(test)
    files.sheet.parent.mkdir(parents=True, exist_ok=True)
    with files.sheet.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for item in items:
            writer.writerow({"item_id": item.item_id, "locale": item.locale, "text": item.text})
    with files.key.open("w", encoding="utf-8", newline="") as stream:
        key_writer = csv.writer(stream)
        key_writer.writerow(("item_id", "assigned_intent", "provenance"))
        key_writer.writerows((item.item_id, item.intent.value, item.provenance) for item in items)
    return "written"


def cohen_kappa(first: list[str], second: list[str]) -> float:
    total = len(first)
    if total == 0:
        return 0.0
    observed = sum(a == b for a, b in zip(first, second, strict=True)) / total
    left, right = Counter(first), Counter(second)
    expected = sum(left[label] * right[label] for label in set(left) | set(right)) / (total * total)
    return 1.0 if expected == 1.0 else (observed - expected) / (1.0 - expected)


def status(files: ValidationFiles) -> dict[str, Any]:
    """Agreement and label accuracy over labeled rows, or ``pending`` when no row is labeled."""
    if not files.sheet.is_file() or not files.key.is_file():
        return {"status": "not exported"}
    with files.sheet.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    with files.key.open(encoding="utf-8") as stream:
        key = {row["item_id"]: row["assigned_intent"] for row in csv.DictReader(stream)}
    both = [row for row in rows if row["labeler_1_intent"].strip() and row["labeler_2_intent"].strip()]
    adjudicated = [row for row in rows if row["adjudicated_intent"].strip()]
    if not both and not adjudicated:
        return {"status": "pending", "items": len(rows)}
    result: dict[str, Any] = {"status": "labeled", "items": len(rows), "double_labeled": len(both)}
    if both:
        result["kappa"] = cohen_kappa(
            [r["labeler_1_intent"].strip() for r in both], [r["labeler_2_intent"].strip() for r in both]
        )
    if adjudicated:
        agree = sum(row["adjudicated_intent"].strip() == key.get(row["item_id"]) for row in adjudicated)
        result["adjudicated"] = len(adjudicated)
        result["label_accuracy"] = agree / len(adjudicated)
    return result
