"""The provider-neutral part of a language model client: prompts in, validated outputs out.

``PromptedLLMClient`` implements the ``LLMClient`` port on top of a ``ChatCompletion`` (one raw chat call to
one model). It renders the prompt through the registry, appends the session language directive and, for a
structured call, the JSON Schema derived from the Pydantic output model. A reply that is not valid JSON or does
not validate gets exactly one repair attempt that quotes the validation errors (field paths and messages,
never input values); a second failure raises ``LlmInvalidOutputError``, which callers handle by falling back
to deterministic behavior. Usage is summed over both attempts.
"""

import json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final, Literal, Protocol

from pydantic import BaseModel, ValidationError

from bank_agent.domain.errors import ConfigurationError, LlmInvalidOutputError
from bank_agent.domain.intelligence import (
    LlmCallContext,
    PromptRef,
    PromptValue,
    RenderedPrompt,
    StructuredGeneration,
    TextGeneration,
    TokenUsage,
)
from bank_agent.domain.locale import Language
from bank_agent.ports.prompts import PromptRegistry

LANGUAGE_DIRECTIVES: Final[Mapping[Language, str]] = {
    Language.ES: "Session language: Spanish (es). Write every customer-facing text in Spanish.",
    Language.PT: (
        "Session language: Brazilian Portuguese (pt-BR). Write every customer-facing text in natural Brazilian "
        "Portuguese, written natively and never translated from Spanish."
    ),
    Language.EN: "Session language: English (en). Write every customer-facing text in English.",
}
JSON_INSTRUCTION: Final = (
    "Reply with exactly one JSON object and nothing else: no prose and no code fences. "
    "It must validate against this JSON Schema:"
)
REPAIR_INSTRUCTION: Final = (
    "Your previous reply did not match the required JSON Schema. Problems: {problems}. "
    "Reply again with only the corrected JSON object."
)
MAX_REPAIR_DETAIL: Final = 1500
_FENCE = re.compile(r"\A```(?:json)?\s*(.*?)\s*```\Z", re.DOTALL)

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    messages: tuple[ChatMessage, ...]
    max_output_tokens: int
    temperature: float
    json_schema: Mapping[str, Any] | None = None
    schema_name: str | None = None


@dataclass(frozen=True, slots=True)
class RawCompletion:
    text: str
    usage: TokenUsage
    model_id: str
    provider_model_id: str | None = None


class ChatCompletion(Protocol):
    """One chat completion against one configured model. Raises only the LLM error family."""

    @property
    def model_id(self) -> str: ...

    async def complete(self, request: CompletionRequest) -> RawCompletion: ...


def _messages(rendered: RenderedPrompt, language: Language, schema: Mapping[str, Any] | None) -> list[ChatMessage]:
    system, user = rendered.messages
    parts = [system.content, LANGUAGE_DIRECTIVES[language]]
    if schema is not None:
        parts.append(f"{JSON_INSTRUCTION}\n{json.dumps(schema, sort_keys=True, ensure_ascii=False)}")
    return [ChatMessage("system", "\n\n".join(parts)), ChatMessage("user", user.content)]


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a reply as one JSON object; floats become ``Decimal`` so amounts stay exact."""
    stripped = text.strip()
    fenced = _FENCE.match(stripped)
    if fenced is not None:
        stripped = fenced[1]
    value = json.loads(stripped, parse_float=Decimal)
    if not isinstance(value, dict):
        raise ValueError("the reply is not a JSON object")
    return value


def describe_problems(error: Exception) -> str:
    """Field paths and messages of a validation failure, without the rejected input values."""
    if isinstance(error, ValidationError):
        details = error.errors(include_url=False, include_input=False, include_context=False)
        text = "; ".join(
            f"{'.'.join(str(part) for part in detail['loc']) or '(root)'}: {detail['msg']}" for detail in details
        )
    else:
        text = "the reply was not a single valid JSON object"
    return text[:MAX_REPAIR_DETAIL]


def check_limits(max_output_tokens: int, temperature: float) -> None:
    """The port preconditions on generation limits; a violation is a programming error, not an LLM error."""
    if max_output_tokens <= 0:
        raise ValueError("max_output_tokens must be positive")
    if not 0.0 <= temperature <= 2.0:
        raise ValueError("temperature must be between 0 and 2")


class PromptedLLMClient:
    """Implements ``LLMClient`` from a prompt registry and a ``ChatCompletion``."""

    def __init__(
        self,
        registry: PromptRegistry,
        completion: ChatCompletion,
        *,
        monotonic: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._registry = registry
        self._completion = completion
        self._monotonic = monotonic

    @property
    def model_id(self) -> str:
        return self._completion.model_id

    def _expect_output(self, prompt: PromptRef, output_model: type[BaseModel] | None) -> None:
        declared = self._registry.get(prompt).output_model
        expected = output_model.__name__ if output_model is not None else None
        if declared != expected:
            raise ConfigurationError(f"{prompt} declares output {declared}, the call expects {expected}")

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
        check_limits(max_output_tokens, temperature)
        self._expect_output(prompt, output_model)
        schema = output_model.model_json_schema()
        messages = _messages(self._registry.render(prompt, variables), language, schema)
        started = self._monotonic()
        raw = await self._complete(messages, max_output_tokens, temperature, schema, output_model.__name__)
        usage = raw.usage
        repaired = False
        try:
            value = output_model.model_validate(parse_json_object(raw.text))
        except (ValueError, ValidationError) as first:
            repaired = True
            messages += [
                ChatMessage("assistant", raw.text),
                ChatMessage("user", REPAIR_INSTRUCTION.format(problems=describe_problems(first))),
            ]
            raw = await self._complete(messages, max_output_tokens, temperature, schema, output_model.__name__)
            usage = usage + raw.usage
            try:
                value = output_model.model_validate(parse_json_object(raw.text))
            except (ValueError, ValidationError):
                raise LlmInvalidOutputError(f"{prompt}: output invalid after one repair attempt") from None
        return StructuredGeneration(
            value=value,
            usage=usage,
            latency_ms=self._elapsed_ms(started),
            model_id=raw.model_id,
            provider_model_id=raw.provider_model_id,
            prompt=prompt,
            repaired=repaired,
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
        check_limits(max_output_tokens, temperature)
        self._expect_output(prompt, None)
        messages = _messages(self._registry.render(prompt, variables), language, None)
        started = self._monotonic()
        raw = await self._complete(messages, max_output_tokens, temperature, None, None)
        text = raw.text.strip()
        if not text:
            raise LlmInvalidOutputError(f"{prompt}: empty text output")
        return TextGeneration(
            text=text,
            usage=raw.usage,
            latency_ms=self._elapsed_ms(started),
            model_id=raw.model_id,
            provider_model_id=raw.provider_model_id,
            prompt=prompt,
        )

    async def _complete(
        self,
        messages: Sequence[ChatMessage],
        max_output_tokens: int,
        temperature: float,
        schema: Mapping[str, Any] | None,
        schema_name: str | None,
    ) -> RawCompletion:
        return await self._completion.complete(
            CompletionRequest(tuple(messages), max_output_tokens, temperature, schema, schema_name)
        )

    def _elapsed_ms(self, started: float) -> int:
        return max(0, round((self._monotonic() - started) * 1000))
