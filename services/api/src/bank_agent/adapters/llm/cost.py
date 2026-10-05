"""Puts a cost on every successful call, from the price table, and emits it as a metric."""

from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.adapters.llm.request import Generation, LlmDecorator, LlmRequest, Proceed
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.telemetry import AttributeValue, Telemetry

COST_METRIC = "bank.llm.cost_usd"


class CostAccountingDecorator(LlmDecorator):
    """Sets ``cost_usd`` on the result and records it in the ``bank.llm.cost_usd`` histogram."""

    def __init__(self, inner: LLMClient, *, prices: PriceTable, telemetry: Telemetry) -> None:
        super().__init__(inner)
        self.prices = prices
        self._histogram = telemetry.histogram(COST_METRIC)

    async def around(self, request: LlmRequest, proceed: Proceed) -> Generation:
        result = await proceed(request)
        cost = self.prices.cost(result.model_id, result.usage)
        basis = self.prices.effective(result.model_id).basis
        attributes: dict[str, AttributeValue] = {
            "gen_ai.response.model": result.model_id,
            "bank.llm.price_basis": basis.value,
            "bank.prompt.id": request.prompt.prompt_id,
        }
        self._histogram.record(float(cost), attributes)
        return result.evolve(cost_usd=cost)
