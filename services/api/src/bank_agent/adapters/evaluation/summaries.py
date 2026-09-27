"""``FilesystemEvaluationSummaries``: the summaries the evaluation harness publishes as JSON files.

Every ``*.json`` file directly in the directory is one ``EvaluationSummary``. A missing directory means nothing is
published yet. A file that does not validate raises ``ConfigurationError`` naming the file, never its content.
"""

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from bank_agent.domain.errors import ConfigurationError
from bank_agent.domain.evaluation import EvaluationSummary

MAX_SUMMARY_BYTES = 1_000_000


def _read(directory: Path) -> list[EvaluationSummary]:
    if not directory.is_dir():
        return []
    summaries: list[EvaluationSummary] = []
    for path in sorted(directory.glob("*.json")):
        if path.stat().st_size > MAX_SUMMARY_BYTES:
            raise ConfigurationError(f"evaluation summary {path.name} is larger than {MAX_SUMMARY_BYTES} bytes")
        try:
            summaries.append(EvaluationSummary.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except (ValueError, ValidationError):
            raise ConfigurationError(f"evaluation summary {path.name} is not a valid summary") from None
    summaries.sort(key=lambda item: (item.run_id, item.system))
    summaries.sort(key=lambda item: item.generated_at, reverse=True)
    return summaries


class FilesystemEvaluationSummaries:
    """Implements ``EvaluationSummaryReader`` over a directory of JSON files."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    async def list(self) -> Sequence[EvaluationSummary]:
        return await asyncio.to_thread(_read, self._directory)
