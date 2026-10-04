#!/usr/bin/env python3
"""Keep ADR file statuses aligned with the ADR index. Stdlib only."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ADR_DIR = ROOT / "docs" / "adr"
_INDEX_LINK = re.compile(r"^\[(\d{4})\]\(([^)]+\.md)\)$")
_PLAIN_STATUS = re.compile(r"^-\s+Status:\s*(.+?)\s*$", re.IGNORECASE)
_BOLD_STATUS = re.compile(r"^\*\s+\*\*Status:\*\*\s*(.+?)\s*$", re.IGNORECASE)
_PARENTHETICAL = re.compile(r"\s*\([^)]*\)\s*$")


def normalize_status(value: str) -> str:
    return _PARENTHETICAL.sub("", value).strip().lower()


def record_status(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines()[:12]:
        match = _PLAIN_STATUS.match(line) or _BOLD_STATUS.match(line)
        if match:
            return normalize_status(match.group(1))
    return None


def index_records(path: Path) -> tuple[dict[str, tuple[Path, str]], list[str]]:
    records: dict[str, tuple[Path, str]] = {}
    problems: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            continue
        match = _INDEX_LINK.match(cells[0])
        if not match:
            continue
        number, file_name = match.groups()
        if number in records:
            problems.append(f"{path}:{line_number}: duplicate ADR number {number}")
            continue
        records[number] = (path.parent / file_name, normalize_status(cells[2]))
    return records, problems


def check(adr_dir: Path = DEFAULT_ADR_DIR) -> list[str]:
    index = adr_dir / "README.md"
    if not index.is_file():
        return [f"{index}: ADR index is missing"]
    records, problems = index_records(index)
    indexed_paths = {path.resolve() for path, _status in records.values()}

    for number, (path, indexed_status) in sorted(records.items()):
        if not path.is_file():
            problems.append(f"{index}: ADR {number} points to missing file {path.name}")
            continue
        if not path.name.startswith(f"{number}-"):
            problems.append(f"{index}: ADR {number} points to mismatched file {path.name}")
        actual_status = record_status(path)
        if actual_status is None:
            problems.append(f"{path}: status line is missing from the first 12 lines")
        elif actual_status != indexed_status:
            problems.append(f"{path}: status '{actual_status}' does not match index status '{indexed_status}'")

    for path in sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        if path.resolve() not in indexed_paths:
            problems.append(f"{path}: ADR is missing from {index}")
    return problems


def main(argv: list[str]) -> int:
    adr_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_ADR_DIR
    problems = check(adr_dir)
    for problem in problems:
        print(problem)
    if problems:
        print(f"check-adr-statuses: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("check-adr-statuses: ADR files and index agree")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
