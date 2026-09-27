"""Bounds the wall-clock time of one attempt; the retry decorator above it decides whether to try again."""

import asyncio

from bank_agent.adapters.llm.request import Generation, LlmDecorator, LlmRequest, Proceed
from bank_agent.domain.errors import LlmTimeoutError
from bank_agent.ports.llm import LLMClient


class TimeoutDecorator(LlmDecorator):
    """Raises ``LlmTimeoutError`` when the inner call takes longer than ``seconds``."""

    def __init__(self, inner: LLMClient, *, seconds: float) -> None:
        if seconds <= 0:
            raise ValueError("the timeout must be positive")
        super().__init__(inner)
        self.seconds = seconds

    async def around(self, request: LlmRequest, proceed: Proceed) -> Generation:
        try:
            async with asyncio.timeout(self.seconds):
                return await proceed(request)
        except TimeoutError:
            raise LlmTimeoutError(f"no reply within {self.seconds} seconds") from None
