#!/usr/bin/env python3
"""Fail if any text file contains emoji characters.

Usage:
    python3 scripts/checks/check_no_emoji.py            # all files tracked by git
    python3 scripts/checks/check_no_emoji.py FILE ...   # specific files (pre-commit mode)

Excluded paths are third-party or generated content that the team does not
author (vendored skills, lockfiles, dependency folders). Binary files are skipped.
"""

from __future__ import annotations

# subprocess runs only git with a fixed argument list (see tracked_files).
import subprocess  # nosec B404
import sys
from pathlib import Path

EMOJI_RANGES: tuple[tuple[int, int], ...] = (
    (0x1F000, 0x1FAFF),  # mahjong, cards, flags, emoticons, pictographs, transport, supplemental, extended-A
    (0x2600, 0x27BF),  # miscellaneous symbols and dingbats
    (0x2B00, 0x2BFF),  # miscellaneous symbols and arrows used as emoji (stars, squares)
    (0x231A, 0x231B),  # watch, hourglass
    (0x23E9, 0x23F3),  # media control symbols
    (0x23F8, 0x23FA),  # media control symbols
    (0xFE0F, 0xFE0F),  # variation selector 16 (emoji presentation)
    (0x20E3, 0x20E3),  # combining enclosing keycap
)

EXCLUDED_PREFIXES: tuple[str, ...] = (
    ".claude/skills/",
    "node_modules/",
    "apps/web/node_modules/",
    "kit/",
    "data/",
)

EXCLUDED_NAMES: frozenset[str] = frozenset(
    {"uv.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"},
)


def is_emoji(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in EMOJI_RANGES)


def is_excluded(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if Path(normalized).name in EXCLUDED_NAMES:
        return True
    return any(normalized.startswith(prefix) or f"/{prefix}" in normalized for prefix in EXCLUDED_PREFIXES)


def tracked_files() -> list[str]:
    # Fixed argument list with no external input; git is resolved from PATH like every other developer tool.
    result = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True)  # nosec B603 B607
    return [p for p in result.stdout.decode("utf-8").split("\0") if p]


def scan(path: str) -> list[tuple[int, int, str]]:
    """Return (line, column, codepoint) for each emoji found; empty for binary or unreadable files."""
    try:
        data = Path(path).read_bytes()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        return []
    if b"\0" in data:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[tuple[int, int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for column, char in enumerate(line, start=1):
            if is_emoji(char):
                findings.append((line_number, column, f"U+{ord(char):04X}"))
    return findings


def main(argv: list[str]) -> int:
    paths = argv[1:] or tracked_files()
    failures = 0
    for path in paths:
        if is_excluded(path):
            continue
        for line_number, column, codepoint in scan(path):
            print(f"{path}:{line_number}:{column}: emoji character {codepoint} is not allowed")
            failures += 1
    if failures:
        print(f"check-no-emoji: {failures} emoji character(s) found", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
