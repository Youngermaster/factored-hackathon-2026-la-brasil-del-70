"""Published evaluation summaries port."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.evaluation import EvaluationSummary


class EvaluationSummaryReader(Protocol):
    """Reads the evaluation summaries the harness has published.

    Postconditions: newest first (``generated_at``, ties broken by ``run_id`` and ``system``); an empty sequence
    when nothing is published yet.
    Errors: a published summary that does not validate raises ``ConfigurationError``; it is never skipped silently.
    """

    async def list(self) -> Sequence[EvaluationSummary]:
        """Return every published summary."""
        ...
