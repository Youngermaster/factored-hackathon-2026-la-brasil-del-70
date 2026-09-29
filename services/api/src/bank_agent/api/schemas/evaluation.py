"""Published evaluation summaries (offline measurements, per workflow and in aggregate)."""

from bank_agent.api.schemas.base import ResponseModel
from bank_agent.domain.evaluation import EvaluationSummary


class EvaluationSummariesResponse(ResponseModel):
    """Newest first. Empty until the evaluation harness publishes a run."""

    summaries: tuple[EvaluationSummary, ...]
