#!/usr/bin/env python3
"""Enforce per-directory line-coverage gates.

Usage:
    python3 scripts/checks/check_coverage_gates.py
    python3 scripts/checks/check_coverage_gates.py --coverage-json PATH --pyproject PATH

coverage.py supports only one global threshold, so the gates live in the ``[tool.bank.coverage-gates]`` table
of ``pyproject.toml``: each key is a path prefix relative to the repository root and each value the minimum
line coverage in percent. The script reads a ``coverage json`` report (combined unit and integration data),
sums covered and total statements per prefix, and prints one line per gate.

A prefix with no measured statements passes and says so explicitly (``no statements yet``), so an empty
layer never passes silently. Exit status is 1 when any gate misses, 2 when an input is missing or malformed,
and 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GateResult:
    prefix: str
    minimum: float
    covered: int
    statements: int

    @property
    def percent(self) -> float | None:
        return None if self.statements == 0 else 100.0 * self.covered / self.statements

    @property
    def passed(self) -> bool:
        percent = self.percent
        return percent is None or percent >= self.minimum

    def describe(self) -> str:
        percent = self.percent
        if percent is None:
            return f"PASS  {self.prefix}: no statements yet (gate {self.minimum:g}%)"
        status = "PASS" if self.passed else "FAIL"
        return f"{status}  {self.prefix}: {percent:.1f}% of {self.statements} statements (gate {self.minimum:g}%)"


class InputError(Exception):
    """An input file is missing or malformed."""


def load_gates(pyproject: Path) -> dict[str, float]:
    """Read the gate table; keys are normalized to have no trailing slash."""
    try:
        document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise InputError(f"cannot read {pyproject}: {error}") from error
    gates = document.get("tool", {}).get("bank", {}).get("coverage-gates")
    if not isinstance(gates, dict) or not gates:
        raise InputError(f"{pyproject} has no [tool.bank.coverage-gates] table")
    normalized: dict[str, float] = {}
    for prefix, minimum in gates.items():
        if not isinstance(minimum, int | float) or isinstance(minimum, bool) or not 0 <= minimum <= 100:
            raise InputError(f"gate for {prefix!r} must be a number between 0 and 100")
        normalized[prefix.rstrip("/")] = float(minimum)
    return normalized


def load_file_summaries(coverage_json: Path) -> dict[str, tuple[int, int]]:
    """Return ``{path: (covered_lines, num_statements)}`` from a coverage JSON report."""
    try:
        report: dict[str, Any] = json.loads(coverage_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InputError(f"cannot read {coverage_json}: {error}") from error
    files = report.get("files")
    if not isinstance(files, dict):
        raise InputError(f"{coverage_json} is not a coverage.py JSON report")
    summaries: dict[str, tuple[int, int]] = {}
    for path, data in files.items():
        summary = data.get("summary", {})
        summaries[path.replace("\\", "/")] = (
            int(summary.get("covered_lines", 0)),
            int(summary.get("num_statements", 0)),
        )
    return summaries


def evaluate(gates: dict[str, float], summaries: dict[str, tuple[int, int]]) -> list[GateResult]:
    results: list[GateResult] = []
    for prefix, minimum in gates.items():
        covered = statements = 0
        for path, (file_covered, file_statements) in summaries.items():
            if path == prefix or path.startswith(prefix + "/"):
                covered += file_covered
                statements += file_statements
        results.append(GateResult(prefix, minimum, covered, statements))
    return results


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Enforce per-directory line-coverage gates.")
    parser.add_argument("--coverage-json", type=Path, default=Path("coverage.json"))
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    args = parser.parse_args(argv[1:])

    try:
        results = evaluate(load_gates(args.pyproject), load_file_summaries(args.coverage_json))
    except InputError as error:
        print(f"check-coverage-gates: {error}", file=sys.stderr)
        return 2

    for result in results:
        print(result.describe())
    failures = [result for result in results if not result.passed]
    if failures:
        print(f"check-coverage-gates: {len(failures)} of {len(results)} gate(s) failed", file=sys.stderr)
        return 1
    print(f"check-coverage-gates: all {len(results)} gate(s) passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
