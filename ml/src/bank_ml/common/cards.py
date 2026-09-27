"""Dataset cards: what a dataset was built from, how it was filtered and split, and a content hash.

Every dataset ``bank-ml`` writes has a card next to it (``card.json`` and ``card.md``), and training logs the card
and hash to MLflow, so a model can always be traced to the exact rows it saw.
"""

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetCard:
    name: str
    version: str
    description: str
    sources: Sequence[str]
    filters: Sequence[str]
    split_method: str
    rows_per_split: Mapping[str, int]
    label_distribution: Mapping[str, Mapping[str, int]]
    content_hash: str
    provenance: Mapping[str, int] = field(default_factory=dict)
    notes: Sequence[str] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    def to_markdown(self) -> str:
        lines = [f"# Dataset card: {self.name}", "", self.description, "", f"- Version: `{self.version}`"]
        lines += [f"- Content hash (SHA-256): `{self.content_hash}`", f"- Split method: {self.split_method}", ""]
        lines += ["## Sources", "", *(f"- {source}" for source in self.sources), ""]
        lines += ["## Filters", "", *(f"- {item}" for item in self.filters), ""]
        lines += ["## Rows per split", "", "| Split | Rows |", "|---|---|"]
        lines += [f"| {split} | {count} |" for split, count in self.rows_per_split.items()]
        labels = sorted({label for counts in self.label_distribution.values() for label in counts})
        splits = list(self.label_distribution)
        lines += ["", "## Label distribution", "", "| Label | " + " | ".join(splits) + " |"]
        lines += ["|---|" + "---|" * len(splits)]
        lines += [
            f"| {label} | " + " | ".join(str(self.label_distribution[s].get(label, 0)) for s in splits) + " |"
            for label in labels
        ]
        if self.provenance:
            lines += ["", "## Provenance", "", "| Provenance | Rows |", "|---|---|"]
            lines += [f"| {kind} | {count} |" for kind, count in sorted(self.provenance.items())]
        if self.notes:
            lines += ["", "## Notes", "", *(f"- {note}" for note in self.notes)]
        return "\n".join(lines) + "\n"

    def write(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "card.json").write_text(self.to_json(), encoding="utf-8")
        (directory / "card.md").write_text(self.to_markdown(), encoding="utf-8")


def label_distribution(rows: Iterable[tuple[str, str]]) -> dict[str, dict[str, int]]:
    """``(split, label)`` pairs -> ``{split: {label: count}}`` with splits in train, dev, test order."""
    counts: dict[str, Counter[str]] = {}
    for split, label in rows:
        counts.setdefault(split, Counter())[label] += 1
    order = [split for split in ("train", "dev", "test") if split in counts] + sorted(
        split for split in counts if split not in {"train", "dev", "test"}
    )
    return {split: dict(sorted(counts[split].items())) for split in order}
