"""The client used when no language model provider is configured.

With ``LLM_PROVIDER=fake`` and no client injected by a test or the evaluation harness, the composition root
uses this adapter. Every call raises ``LlmProviderRejectedError``, which is never retried, so the workflows run
on their documented deterministic fallbacks (clarify, abstain, or hand off) instead of guessing.
"""

from collections.abc import Mapping

from pydantic import BaseModel

from bank_agent.domain.errors import LlmProviderRejectedError
from bank_agent.domain.intelligence import (
    LlmCallContext,
    PromptRef,
    PromptValue,
    StructuredGeneration,
    TextGeneration,
)
from bank_agent.domain.locale import Language

MESSAGE = "no language model provider is configured"


class UnconfiguredLLMClient:
    """Implements ``LLMClient`` by refusing every call with a typed, non-retryable error."""

    model_id = "none/unconfigured"

    async def generate_structured[OutputT: BaseModel](
        self,
        prompt: PromptRef,
        variables: Mapping[str, PromptValue],
        output_model: type[OutputT],
        *,
        language: Language,
        max_output_tokens: int,
        temperature: float,
        call_context: LlmCallContext,
    ) -> StructuredGeneration[OutputT]:
        raise LlmProviderRejectedError(MESSAGE)

    async def generate_text(
        self,
        prompt: PromptRef,
        variables: Mapping[str, PromptValue],
        *,
        language: Language,
        max_output_tokens: int,
        temperature: float,
        call_context: LlmCallContext,
    ) -> TextGeneration:
        raise LlmProviderRejectedError(MESSAGE)
