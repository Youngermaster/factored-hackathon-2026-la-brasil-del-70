"""``FilesystemModelCards``: the curated model cards in ``services/api/config/model_cards.yaml``.

The file is a reviewed copy of the generated model reports (``docs/models/*.md``, ``docs/evaluation/*.md``). A missing
file means nothing is published (an empty set). A file that is too large or does not validate raises
``ConfigurationError`` naming the file, never its content.
"""

import asyncio
from pathlib import Path

import yaml
from pydantic import ValidationError

from bank_agent.domain.errors import ConfigurationError
from bank_agent.domain.model_inventory import EMPTY_CARD_SET, ModelCardSet

MAX_CARDS_BYTES = 256_000


def _read(path: Path) -> ModelCardSet:
    if not path.is_file():
        return EMPTY_CARD_SET
    if path.stat().st_size > MAX_CARDS_BYTES:
        raise ConfigurationError(f"model cards {path.name} is larger than {MAX_CARDS_BYTES} bytes")
    try:
        return ModelCardSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, yaml.YAMLError, ValidationError):
        raise ConfigurationError(f"model cards {path.name} is not a valid card set") from None


class FilesystemModelCards:
    """Implements ``ModelCardReader`` over one YAML file, read on every call (the file is small)."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def read(self) -> ModelCardSet:
        return await asyncio.to_thread(_read, self._path)
