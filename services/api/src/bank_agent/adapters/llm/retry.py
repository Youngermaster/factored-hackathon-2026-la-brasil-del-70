"""Bounded retry for transient failures only.

Only errors whose class is ``retryable`` (timeout, rate limited, provider error) are retried, at most twice,
with exponential backoff and jitter: the delay before retry ``n`` (0-based) is
``min(max_delay, base_delay * 2**n)`` scaled by a factor in ``[0.5, 1.0)``. Invalid output is never retried here:
the provider client already made its single repair attempt. A provider rejection is not retryable either.
"""

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from typing import Final

from bank_agent.adapters.llm.request import Generation, LlmDecorator, LlmRequest, Proceed
from bank_agent.domain.errors import LlmError
from bank_agent.ports.llm import LLMClient

MAX_RETRIES_ALLOWED: Final = 2
_SYSTEM_RANDOM: Final = secrets.SystemRandom()
Sleep = Callable[[float], Awaitable[None]]


class BoundedRetryDecorator(LlmDecorator):
    """Retries transient LLM errors with exponential backoff and jitter."""

    def __init__(
        self,
        inner: LLMClient,
        *,
        max_retries: int = MAX_RETRIES_ALLOWED,
        base_delay_seconds: float = 0.5,
        max_delay_seconds: float = 4.0,
        sleep: Sleep = asyncio.sleep,
        jitter: Callable[[], float] = _SYSTEM_RANDOM.random,
    ) -> None:
        if not 0 <= max_retries <= MAX_RETRIES_ALLOWED:
            raise ValueError(f"max_retries must be between 0 and {MAX_RETRIES_ALLOWED}")
        if base_delay_seconds < 0 or max_delay_seconds < base_delay_seconds:
            raise ValueError("delays must satisfy 0 <= base_delay <= max_delay")
        super().__init__(inner)
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self._sleep = sleep
        self._jitter = jitter

    def delay_for(self, retry: int) -> float:
        """The delay before retry number ``retry`` (0-based)."""
        ceiling = min(self.max_delay_seconds, self.base_delay_seconds * 2.0**retry)
        return ceiling * (0.5 + self._jitter() / 2)

    async def around(self, request: LlmRequest, proceed: Proceed) -> Generation:
        retry = 0
        while True:
            try:
                return await proceed(request)
            except LlmError as error:
                if not error.retryable or retry >= self.max_retries:
                    raise
                await self._sleep(self.delay_for(retry))
                retry += 1
