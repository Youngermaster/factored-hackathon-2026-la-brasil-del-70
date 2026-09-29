"""The committed scenario files and the test set lock.

- ``evals/data/scenarios.dev.jsonl`` and ``evals/data/scenarios.test.jsonl``: one scenario per line, sorted by id,
  keys sorted, so the same scenarios always give the same bytes.
- ``evals/data/test_set.lock``: the SHA-256 of the test file. The test split is frozen: a test fails when the file
  changes without the lock, and ``bank-eval scenarios lock`` refuses to move it unless asked explicitly.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from bank_evals.scenarios.model import Scenario, Split

DATA_DIR: Final = Path(__file__).resolve().parents[3] / "data"
LOCK_FILE: Final = DATA_DIR / "test_set.lock"


class LockMismatchError(RuntimeError):
    """The frozen test split does not match its lock."""


def split_path(split: Split, directory: Path = DATA_DIR) -> Path:
    return directory / f"scenarios.{split.value}.jsonl"


def dumps(scenarios: Sequence[Scenario]) -> str:
    lines = [
        json.dumps(s.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        for s in sorted(scenarios, key=lambda s: s.id)
    ]
    return "\n".join(lines) + "\n"


def write_split(scenarios: Sequence[Scenario], path: Path) -> None:
    path.write_text(dumps(scenarios), encoding="utf-8")


def load_split(path: Path) -> list[Scenario]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Scenario.model_validate_json(line) for line in lines if line.strip()]


def content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_lock(test_file: Path, lock: Path = LOCK_FILE) -> str:
    digest = content_hash(test_file)
    lock.write_text(f"{digest}  {test_file.name}\n", encoding="utf-8")
    return digest


def read_lock(lock: Path = LOCK_FILE) -> str:
    return lock.read_text(encoding="utf-8").split()[0]


def check_lock(test_file: Path, lock: Path = LOCK_FILE) -> str:
    """The locked hash; ``LockMismatchError`` when the test file differs from it."""
    expected, actual = read_lock(lock), content_hash(test_file)
    if expected != actual:
        raise LockMismatchError(f"{test_file.name} changed: locked {expected[:12]}, found {actual[:12]}")
    return expected
