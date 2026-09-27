"""Salted hashes for split assignment and content digests for dataset cards and tracking."""

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def salted_unit(salt: str, key: str) -> float:
    """A number in [0, 1) from SHA-256 of ``salt:key``: uniform, stable, and independent of the key's order."""
    digest = hashlib.sha256(f"{salt}:{key}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def salted_order(salt: str, key: str) -> str:
    return hashlib.sha256(f"{salt}:{key}".encode()).hexdigest()


def rows_digest(rows: Iterable[Mapping[str, Any]]) -> str:
    """SHA-256 over the canonical JSON of every row, in order."""
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
