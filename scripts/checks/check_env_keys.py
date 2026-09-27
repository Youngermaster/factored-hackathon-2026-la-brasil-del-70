#!/usr/bin/env python3
"""Report which documented environment variables are set, without revealing any value.

Usage:
    python3 scripts/checks/check_env_keys.py
    python3 scripts/checks/check_env_keys.py --env-file PATH --example PATH

Variable names come from `.env.example`, which documents every setting. A
variable counts as set when it is non-empty in the process environment or in
the env file. The script only tests each value for emptiness: it never prints,
logs, or returns a value, and its messages never include file content.

Exit status is 1 when any name in REQUIRED is unset, and 0 otherwise.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Variables that must be set before the data and persistence phases can run.
# The LLM keys stay optional while LLM_PROVIDER=fake; they move here once the human chooses a live provider.
REQUIRED: tuple[str, ...] = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_DEFAULT_REGION",
    "DATA_BUCKET",
    "DATA_PREFIX",
    "POSTGRES_ADMIN_PASSWORD",
    "POSTGRES_APP_PASSWORD",
    "SESSION_SECRET",
    "CSRF_SECRET",
)

NAME_PATTERN = re.compile(r"^(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=(.*)$")


def example_names(example_path: Path) -> list[str]:
    """Return variable names declared in the example file, in order, without duplicates."""
    names: list[str] = []
    for line in example_path.read_text(encoding="utf-8").splitlines():
        match = NAME_PATTERN.match(line.strip())
        if match and match.group(1) not in names:
            names.append(match.group(1))
    return names


def _is_non_empty(raw: str) -> bool:
    """Decide whether a raw env-file value is non-empty after quotes and comments are removed."""
    value = raw.strip()
    if value[:1] in {'"', "'"}:
        quote = value[0]
        closing = value.find(quote, 1)
        inner = value[1:closing] if closing != -1 else value[1:]
        return bool(inner.strip())
    value = re.split(r"\s+#", value, maxsplit=1)[0] if not value.startswith("#") else ""
    return bool(value.strip())


def names_set_in_file(env_path: Path) -> set[str]:
    """Return the names that have a non-empty value in the env file."""
    present: set[str] = set()
    for line in env_path.read_text(encoding="utf-8").splitlines():
        match = NAME_PATTERN.match(line.strip())
        if match and _is_non_empty(match.group(2)):
            present.add(match.group(1))
    return present


def names_set_in_process(names: list[str]) -> set[str]:
    """Return the names that have a non-empty value in the process environment."""
    return {name for name in names if os.environ.get(name, "").strip()}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Report set or unset for documented environment variables.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="env file to inspect (default: .env)")
    parser.add_argument(
        "--example",
        type=Path,
        default=Path(".env.example"),
        help="file that documents the names (default: .env.example)",
    )
    args = parser.parse_args(argv[1:])

    if not args.example.is_file():
        print(f"check-env-keys: example file not found: {args.example}", file=sys.stderr)
        return 2

    names = example_names(args.example)
    for name in REQUIRED:
        if name not in names:
            names.append(name)

    present = names_set_in_process(names)
    if args.env_file.is_file():
        present |= names_set_in_file(args.env_file)
    else:
        print(f"check-env-keys: {args.env_file} not found; checking the process environment only")

    required = [name for name in names if name in REQUIRED]
    optional = [name for name in names if name not in REQUIRED]

    print("Required:")
    for name in required:
        print(f"  {name}: {'set' if name in present else 'unset'}")
    print("Optional:")
    for name in optional:
        print(f"  {name}: {'set' if name in present else 'unset'}")

    missing = [name for name in required if name not in present]
    if missing:
        print(f"check-env-keys: {len(missing)} of {len(required)} required variable(s) unset")
        return 1
    print(f"check-env-keys: all {len(required)} required variable(s) set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
