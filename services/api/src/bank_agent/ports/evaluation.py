"""Published evaluation summaries port."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.evaluation import EvaluationSummary


class EvaluationSummaryReader(Protocol):
    """Reads the evaluation summaries the harness has published.

    Preconditions: none; summaries are aggregate offline measurements with no customer data, so any caller may read
    them (the HTTP layer decides who may).
    Postconditions: newest first (``generated_at``, ties broken by ``run_id`` and ``system``); an empty sequence
    when nothing is published yet.
    Errors: a published summary that does not validate raises ``ConfigurationError``; it is never skipped silently.
    Isolation: not applicable; a summary holds counts and rates over a workload, never a customer record.
    """

    async def list(self) -> Sequence[EvaluationSummary]:
        """Return every published summary."""
        ...
