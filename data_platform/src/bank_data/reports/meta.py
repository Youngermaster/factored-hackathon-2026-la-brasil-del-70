"""Report metadata: the generation instant and the git commit, without secrets or absolute paths."""

import shutil
import subprocess  # nosec B404 (runs git from PATH with a fixed argument list)
from datetime import UTC, datetime

from bank_data.settings import REPOSITORY_ROOT


def generated_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def git_sha() -> str:
    """The short commit of the working tree, with ``-dirty`` when it has uncommitted changes; ``unknown``
    outside a git checkout."""
    git = shutil.which("git")
    if git is None:
        return "unknown"
    try:
        sha = subprocess.run(  # noqa: S603  # nosec B603 (fixed arguments)
            [git, "rev-parse", "--short", "HEAD"], cwd=REPOSITORY_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        status = subprocess.run(  # noqa: S603  # nosec B603 (fixed arguments)
            [git, "status", "--porcelain", "--untracked-files=no"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if status else sha
