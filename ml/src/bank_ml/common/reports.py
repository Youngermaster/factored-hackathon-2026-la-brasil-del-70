"""Report helpers: generation metadata (instant, git commit) and small Markdown builders."""

import shutil
import subprocess  # nosec B404 (runs git from PATH with a fixed argument list)
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def generated_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def git_sha(root: Path = REPOSITORY_ROOT) -> str:
    """The short commit, with ``-dirty`` when tracked files changed; ``unknown`` outside a git checkout."""
    git = shutil.which("git")
    if git is None:
        return "unknown"
    try:
        sha = subprocess.run(  # noqa: S603  # nosec B603 (fixed arguments)
            [git, "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
        status = subprocess.run(  # noqa: S603  # nosec B603 (fixed arguments)
            [git, "status", "--porcelain", "--untracked-files=no"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if status else sha


def table(header: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return lines


def pct(value: float, digits: int = 1) -> str:
    return f"{100 * value:.{digits}f}%"
