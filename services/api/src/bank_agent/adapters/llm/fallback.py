"""Primary provider, then the fallback provider, then a typed failure.

Any LLM error from the primary stack (after its own breaker, retries, and timeout) sends the same request to the
fallback stack. If the fallback fails too, its typed error is raised, chained to the primary's. A budget error
never triggers the fallback, because a second provider would spend the same budget.
"""

from bank_agent.adapters.llm.request import Generation, LlmDecorator, LlmRequest, Proceed, dispatch
from bank_agent.domain.errors import LlmBudgetExceededError, LlmError
from bank_agent.ports.llm import LLMClient


class FallbackDecorator(LlmDecorator):
    """``inner`` is the primary stack; ``fallback`` is used when it fails."""

    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        super().__init__(primary)
        self.fallback = fallback

    async def around(self, request: LlmRequest, proceed: Proceed) -> Generation:
        try:
            return await proceed(request)
        except LlmBudgetExceededError:
            raise
        except LlmError as primary_error:
            try:
                return await dispatch(self.fallback, request)
            except LlmError as fallback_error:
                raise fallback_error from primary_error
