"""Published evaluation summaries port."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.evaluation import EvaluationSummary


class EvaluationSummaryReader(Protocol):
    """Reads the evaluation summaries the harness has published.

    Preconditions: the summaries are published by the evaluation harness before the API reads them; the reader
    never writes or recomputes them.
    Postconditions: newest first (``generated_at``, ties broken by ``run_id`` and ``system``); an empty sequence
    when nothing is published yet.
    Errors: a published summary that does not validate raises ``ConfigurationError``; it is never skipped silently.
    Isolation: summaries hold aggregate metrics only, no customer data; the API layer decides who may read them
    (an evaluator session unless ``EVAL_SUMMARIES_PUBLIC=true``).
    """

    async def list(self) -> Sequence[EvaluationSummary]:
        """Return every published summary."""
        ...
