"""Read the policy pack directory into a mapping of relative POSIX path to text."""

from pathlib import Path

from bank_agent.domain.errors import PolicyPackInvalidError

PACK_SUFFIXES = frozenset({".md", ".yaml"})


def read_pack_files(root: Path) -> dict[str, str]:
    """Every ``.md`` and ``.yaml`` file under ``root``, keyed by its path relative to ``root``."""
    if not root.is_dir():
        raise PolicyPackInvalidError("the policy pack directory does not exist")
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in PACK_SUFFIXES:
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return files
