#!/usr/bin/env python3
"""commit-msg hook: remove AI tool attribution lines from a commit message.

Git passes the path of the commit message file as the first argument. The hook
rewrites that file in place, removing co-author trailers and "generated with"
footers added by AI coding tools, then trims trailing blank lines.

It exits 0 so the commit proceeds with the cleaned message. The CI check
scripts/checks/check_no_ai_attribution.sh is the second line of defense.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ATTRIBUTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*co-authored-by:.*\b(claude|anthropic|copilot|chatgpt|openai|gemini|cursor)\b.*$", re.IGNORECASE),
    re.compile(r"^\s*co-authored-by:.*noreply@anthropic\.com.*$", re.IGNORECASE),
    re.compile(r"^.*\bgenerated (with|by) \[?(claude|claude code|an ai|ai)\]?.*$", re.IGNORECASE),
    re.compile(r"^.*\bclaude\.(ai|com)/(code|claude-code)\b.*$", re.IGNORECASE),
)


def clean_message(text: str) -> str:
    """Return the message without attribution lines and without trailing blank lines."""
    kept = [line for line in text.splitlines() if not any(p.match(line) for p in ATTRIBUTION_PATTERNS)]
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept) + "\n" if kept else ""


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: strip_ai_attribution.py <commit-message-file>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    original = path.read_text(encoding="utf-8")
    cleaned = clean_message(original)
    if cleaned != original:
        path.write_text(cleaned, encoding="utf-8")
        print("strip-ai-attribution: removed attribution lines from the commit message", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
