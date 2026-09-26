"""Language model client port (phase 08 adds the providers and the decorators)."""

from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel

from bank_agent.domain.intelligence import (
    LlmCallContext,
    PromptRef,
    PromptValue,
    StructuredGeneration,
    TextGeneration,
)
from bank_agent.domain.locale import Language


class LLMClient(Protocol):
    """Structured and plain text generation from versioned prompts.

    Preconditions: ``variables`` match the prompt's declared inputs; untrusted text arrives as
    ``UntrustedText`` and the prompt declares it as data. ``temperature`` is between 0 and 2.
    Postconditions: results carry token usage, latency, the model id, the prompt reference, and (after cost
    accounting) the cost. A structured result is a validated instance of ``output_model``; ``repaired`` is
    true when the single repair attempt was used.
    Errors: only the LLM error family: ``LlmTimeoutError``, ``LlmRateLimitedError``, ``LlmProviderError``,
    ``LlmInvalidOutputError``, ``LlmBudgetExceededError``, ``LlmCircuitOpenError``. Callers must handle every
    one by falling back to deterministic behavior.
    Isolation: implementations never receive customer identifiers, names, document numbers, or contact
    details; the redaction decorator enforces an allowlist of variable keys.
    """

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
        """Generate and validate a structured output."""
        ...

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
        """Generate plain text."""
        ...
