"""Shared support for the LLM gateway tests: a scripted chat completion, a controllable client, and call helpers.

Nothing here talks to a network. ``ScriptedCompletion`` returns queued raw replies (or raises queued errors) and
records every request, so tests can assert on the exact messages the gateway would send.
"""

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from bank_agent.adapters.llm.client import CompletionRequest, RawCompletion
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import LlmError
from bank_agent.domain.intelligence import (
    LlmCallContext,
    PromptRef,
    PromptValue,
    StructuredGeneration,
    TextGeneration,
    TokenUsage,
)
from bank_agent.domain.locale import Language
from bank_agent.ports.llm import LLMClient

DISPUTE_PROMPT = PromptRef.model_validate("extract_dispute_slots@1")
PHRASE_PROMPT = PromptRef.model_validate("phrase_response@1")
SIGNALS_PROMPT = PromptRef.model_validate("detect_escalation_signals@1")
CONTEXT = LlmCallContext()


def dispute_variables(message: str = "No reconozco un cargo de 1500 pesos en Oxxo") -> dict[str, PromptValue]:
    return {"customer_message": UntrustedText(message), "reference_date": "2026-09-26", "dialect_hint": "es-MX"}


def phrase_variables(facts: Sequence[str] = ("Saldo disponible: 1200.00 MXN al 2026-09-26",)) -> dict[str, PromptValue]:
    return {
        "workflow": "account_inquiry",
        "response_kind": "answer",
        "facts": list(facts),
        "clause_texts": ["Los saldos se informan con su fecha de corte."],
        "dialect_hint": "es-MX",
    }


class SimpleOutput(BaseModel):
    """A tiny output model for decorator tests that do not go through the prompt registry."""

    answer: str


@dataclass
class ScriptedCompletion:
    """A ``ChatCompletion`` that returns queued replies; the last one repeats."""

    replies: list[str | LlmError]
    model: str = "test/scripted"
    usage: TokenUsage = field(default_factory=lambda: TokenUsage(input_tokens=100, output_tokens=20))
    requests: list[CompletionRequest] = field(default_factory=list)

    @property
    def model_id(self) -> str:
        return self.model

    async def complete(self, request: CompletionRequest) -> RawCompletion:
        self.requests.append(request)
        reply = self.replies[min(len(self.requests) - 1, len(self.replies) - 1)]
        if isinstance(reply, LlmError):
            raise reply
        return RawCompletion(text=reply, usage=self.usage, model_id=self.model)


@dataclass
class StubClient:
    """An ``LLMClient`` whose behavior per call is a queue of results or errors; the last entry repeats.

    A result entry is ``"ok"``; the client then returns a generation with ``usage`` and ``model_id``. A
    ``delay`` makes each call sleep first (for timeout tests).
    """

    outcomes: list[str | LlmError] = field(default_factory=lambda: ["ok"])
    model_id: str = "stub/model"
    usage: TokenUsage = field(default_factory=lambda: TokenUsage(input_tokens=1000, output_tokens=200))
    delay: float = 0.0
    cost_usd: Decimal | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def _next(self, variables: Mapping[str, PromptValue], context: LlmCallContext) -> None:
        self.calls.append({"variables": dict(variables), "context": context})
        outcome = self.outcomes[min(len(self.calls) - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, LlmError):
            raise outcome

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
        if self.delay:
            await asyncio.sleep(self.delay)
        self._next(variables, call_context)
        value = output_model.model_validate({"answer": "yes"})
        return StructuredGeneration(
            value=value,
            usage=self.usage,
            latency_ms=5,
            model_id=self.model_id,
            prompt=prompt,
            cost_usd=self.cost_usd,
        )

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
        if self.delay:
            await asyncio.sleep(self.delay)
        self._next(variables, call_context)
        return TextGeneration(
            text="hola", usage=self.usage, latency_ms=5, model_id=self.model_id, prompt=prompt, cost_usd=self.cost_usd
        )


async def call_structured(
    client: LLMClient,
    *,
    variables: Mapping[str, PromptValue] | None = None,
    context: LlmCallContext = CONTEXT,
    max_output_tokens: int = 500,
) -> StructuredGeneration[SimpleOutput]:
    return await client.generate_structured(
        PHRASE_PROMPT,
        variables if variables is not None else {"customer_message": "hola"},
        SimpleOutput,
        language=Language.ES,
        max_output_tokens=max_output_tokens,
        temperature=0.0,
        call_context=context,
    )


async def call_text(
    client: LLMClient,
    *,
    variables: Mapping[str, PromptValue] | None = None,
    context: LlmCallContext = CONTEXT,
    max_output_tokens: int = 500,
) -> TextGeneration:
    return await client.generate_text(
        PHRASE_PROMPT,
        variables if variables is not None else {"customer_message": "hola"},
        language=Language.ES,
        max_output_tokens=max_output_tokens,
        temperature=0.0,
        call_context=context,
    )
