"""Published evaluation ports: the run summaries and the curated model cards."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.evaluation import EvaluationSummary
from bank_agent.domain.model_inventory import ModelCardSet


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


class ModelCardReader(Protocol):
    """Reads the curated model cards and promotion decisions (offline metrics on synthetic data).

    Preconditions: the cards are a committed, reviewed copy of the generated model reports; the reader never
    computes or edits a metric.
    Postconditions: the validated set; an empty set when no file is published.
    Errors: a file that does not validate raises ``ConfigurationError`` naming the file, never its content.
    Isolation: cards hold model ids, published metrics, and repository paths only, no customer data; the API layer
    serves them to evaluator sessions.
    """

    async def read(self) -> ModelCardSet:
        """Return the published cards."""
        ...
