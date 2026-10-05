"""Published evaluation summaries, per workflow and in aggregate, each labeled offline, simulated, or projected; and
the model inventory with its offline model cards."""

from bank_agent.api.schemas.base import ResponseModel
from bank_agent.domain.evaluation import EvaluationSummary
from bank_agent.domain.model_inventory import ModelCardSet, ModelInventory


class EvaluationSummariesResponse(ResponseModel):
    """Newest first. Empty until the evaluation harness publishes a run."""

    summaries: tuple[EvaluationSummary, ...]


class ModelInventoryResponse(ResponseModel):
    """What the process serves, recorded at startup, and the published offline evidence for each model.

    ``inventory`` is configuration (no customer data, identifiers, endpoints, or keys); ``cards`` are offline
    metrics on synthetic data and simulated end-to-end promotion decisions, never production measurements.
    """

    inventory: ModelInventory
    cards: ModelCardSet
