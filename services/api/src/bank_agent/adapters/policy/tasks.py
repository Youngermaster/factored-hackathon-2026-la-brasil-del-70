"""Maintenance tasks over the pack directory: rewrite the version lock and regenerate the policy catalog page."""

import shutil
import subprocess  # nosec B404 (runs git from PATH with a fixed argument list)
from datetime import UTC, datetime
from pathlib import Path

from bank_agent.adapters.policy.files import read_pack_files
from bank_agent.policy.catalog_doc import render_catalog
from bank_agent.policy.loader import load_pack
from bank_agent.policy.loader.catalog import check_catalog_against_pack, parse_catalog
from bank_agent.policy.loader.lock import LOCK_PATH, render_lock


def write_lock(root: Path) -> Path:
    """Rewrite ``versions.lock.yaml``; raises ``ValueError`` if a changed clause kept its version.

    The pack is validated with the new lock before the file is written.
    """
    files = read_pack_files(root)
    text = render_lock(files)
    load_pack({**files, LOCK_PATH: text})
    target = root / LOCK_PATH
    target.write_text(text, encoding="utf-8")
    return target


def git_sha(cwd: Path) -> str:
    """The short commit, with ``-dirty`` for uncommitted changes; ``unknown`` outside a git checkout."""
    git = shutil.which("git")
    if git is None:
        return "unknown"
    try:
        sha = subprocess.run(  # noqa: S603  # nosec B603 (fixed arguments)
            [git, "rev-parse", "--short", "HEAD"], cwd=cwd, capture_output=True, text=True, check=True
        ).stdout.strip()
        status = subprocess.run(  # noqa: S603  # nosec B603 (fixed arguments)
            [git, "status", "--porcelain", "--untracked-files=no"], cwd=cwd, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if status else sha


def write_catalog(root: Path, output: Path) -> Path:
    """Render the policy catalog page from the pack and the credit catalog."""
    files = read_pack_files(root)
    pack = load_pack(files)
    entries = parse_catalog(files)
    check_catalog_against_pack(entries, pack)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_catalog(pack, entries, generated_at=generated_at, commit=git_sha(root)), encoding="utf-8")
    return output
