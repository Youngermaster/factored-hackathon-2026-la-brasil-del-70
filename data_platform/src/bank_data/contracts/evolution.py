"""Schema-evolution detection: compare a batch's observed schema with the contract.

- **Additive**: the batch has columns the contract does not know. Bronze accepts them as nullable strings, a
  warning is logged, and a backlog item is recorded in the manifest database.
- **Breaking**: the batch lacks a contract column (``removed_column``) or a contract column changed type
  (``type_change``: at least ``type_change_threshold`` of its non-empty values fail to parse). The whole batch
  is quarantined and the run exits with ``SchemaEvolutionError``.
- **Unchanged**: exactly the contract columns, every type intact.

Column names are compared after trimming and lowercasing, the way the organizer headers are written.
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from bank_data.contracts.parsing import ParsedColumn, failure_share
from bank_data.contracts.tables import TableSpec

DEFAULT_TYPE_CHANGE_THRESHOLD = 0.5


class ChangeKind(StrEnum):
    UNCHANGED = "unchanged"
    ADDITIVE = "additive"
    BREAKING = "breaking"


@dataclass(frozen=True)
class SchemaChange:
    kind: ChangeKind
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    type_changes: tuple[str, ...] = ()
    failure_shares: Mapping[str, float] = field(default_factory=dict)

    @property
    def reason_code(self) -> str | None:
        if self.removed:
            return "schema_removed_column"
        if self.type_changes:
            return "schema_type_change"
        if self.added:
            return "schema_additive_column"
        return None

    def describe(self) -> str:
        parts = []
        if self.removed:
            parts.append(f"removed columns: {', '.join(self.removed)}")
        if self.type_changes:
            parts.append(f"type changes: {', '.join(self.type_changes)}")
        if self.added:
            parts.append(f"added columns: {', '.join(self.added)}")
        return "; ".join(parts) if parts else "no change"


def normalize_name(name: str) -> str:
    return name.strip().lstrip("﻿").lower()


def schema_hash(columns: Sequence[str]) -> str:
    """A stable hash of the observed header (order-sensitive, names normalized)."""
    joined = "\x1f".join(normalize_name(name) for name in columns)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def compare_columns(observed: Sequence[str], spec: TableSpec) -> SchemaChange:
    """Classify the header alone: added and removed columns."""
    seen = [normalize_name(name) for name in observed]
    expected = list(spec.column_names)
    added = tuple(name for name in seen if name not in expected)
    removed = tuple(name for name in expected if name not in seen)
    if removed:
        return SchemaChange(ChangeKind.BREAKING, added=added, removed=removed)
    if added:
        return SchemaChange(ChangeKind.ADDITIVE, added=added)
    return SchemaChange(ChangeKind.UNCHANGED)


def detect_type_changes(
    header_change: SchemaChange,
    parsed: Mapping[str, ParsedColumn],
    *,
    threshold: float = DEFAULT_TYPE_CHANGE_THRESHOLD,
) -> SchemaChange:
    """Add type changes to a header classification. String columns never change type."""
    shares = {name: failure_share(column) for name, column in parsed.items()}
    changed = tuple(name for name, share in shares.items() if share >= threshold and share > 0)
    if not changed:
        return SchemaChange(
            header_change.kind,
            added=header_change.added,
            removed=header_change.removed,
            failure_shares=shares,
        )
    return SchemaChange(
        ChangeKind.BREAKING,
        added=header_change.added,
        removed=header_change.removed,
        type_changes=changed,
        failure_shares=shares,
    )
