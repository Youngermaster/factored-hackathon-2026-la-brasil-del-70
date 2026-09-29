"""Published evaluation summaries, per workflow and in aggregate, each labeled offline, simulated, or projected."""

from bank_agent.api.schemas.base import ResponseModel
from bank_agent.domain.evaluation import EvaluationSummary


class EvaluationSummariesResponse(ResponseModel):
    """Newest first. Empty until the evaluation harness publishes a run."""

    summaries: tuple[EvaluationSummary, ...]
