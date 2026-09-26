"""A scripted language model client.

Responses are scripted per prompt reference and per input hash (a SHA-256 over the prompt reference and the
canonical JSON of the variables), or per prompt with a wildcard. Each script is a queue: calls consume
entries in order and the last entry repeats, so "fail once, then succeed" is one script. An unscripted call
raises ``FakeLLMScriptMissingError`` loudly; the fake never guesses.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import BaseModel, JsonValue, ValidationError

from bank_agent.domain.errors import LlmError, LlmInvalidOutputError
from bank_agent.domain.intelligence import (
    LlmCallContext,
    PromptRef,
    PromptValue,
    StructuredGeneration,
    TextGeneration,
    TokenUsage,
)
from bank_agent.domain.locale import Language
from bank_agent.domain.money import Money

WILDCARD = "*"
DEFAULT_MODEL_ID = "fake/scripted"


class FakeLLMScriptMissingError(Exception):
    """A call had no script. Tests must script every call they make."""


def _canonical(value: PromptValue) -> JsonValue:
    if isinstance(value, Money):
        return {"amount": str(value.amount), "currency": value.currency.value}
    if isinstance(value, Decimal):
        return str(value)
    if value is None or isinstance(value, str | int | bool):
        return value
    return [str(item) for item in value]


def canonical_variables(variables: Mapping[str, PromptValue]) -> str:
    """Canonical JSON for ``variables``: sorted keys, Decimal and Money as strings, no whitespace."""
    normalized = {key: _canonical(value) for key, value in variables.items()}
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def input_hash(prompt: PromptRef, variables: Mapping[str, PromptValue]) -> str:
    """The key the fake (and the phase 08 cassette client) uses for one call."""
    payload = f"{prompt}\n{canonical_variables(variables)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ScriptedResponse:
    """A successful response: a mapping for structured calls, a string for text calls."""

    output: Mapping[str, JsonValue] | str
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: int = 0
    model_id: str = DEFAULT_MODEL_ID
    cost_usd: Decimal | None = None
    repaired: bool = False


@dataclass(frozen=True, slots=True)
class ScriptedError:
    """A failure: the call raises an instance of ``error``."""

    error: type[LlmError]


Script = ScriptedResponse | ScriptedError


@dataclass(frozen=True, slots=True)
class FakeLLMCall:
    prompt: PromptRef
    variables: Mapping[str, PromptValue]
    input_hash: str
    language: Language
    call_context: LlmCallContext
    structured: bool


class FakeLLM:
    """Implements the ``LLMClient`` port from scripts. ``calls`` records every call for assertions."""

    def __init__(self) -> None:
        self._scripts: dict[tuple[str, int, str], list[Script]] = {}
        self._positions: dict[tuple[str, int, str], int] = {}
        self.calls: list[FakeLLMCall] = []

    def script(
        self,
        prompt: PromptRef,
        *responses: Script,
        variables: Mapping[str, PromptValue] | None = None,
    ) -> None:
        """Queue ``responses`` for ``prompt``; for exactly ``variables`` when given, otherwise for any input."""
        if not responses:
            raise ValueError("script at least one response")
        digest = input_hash(prompt, variables) if variables is not None else WILDCARD
        self._scripts.setdefault((prompt.prompt_id, prompt.version, digest), []).extend(responses)

    def _next(self, prompt: PromptRef, digest: str) -> Script:
        for key in ((prompt.prompt_id, prompt.version, digest), (prompt.prompt_id, prompt.version, WILDCARD)):
            queue = self._scripts.get(key)
            if queue:
                position = self._positions.get(key, 0)
                self._positions[key] = position + 1
                return queue[min(position, len(queue) - 1)]
        raise FakeLLMScriptMissingError(f"no script for {prompt} with input hash {digest}")

    def _call(
        self,
        prompt: PromptRef,
        variables: Mapping[str, PromptValue],
        language: Language,
        call_context: LlmCallContext,
        *,
        structured: bool,
    ) -> ScriptedResponse:
        digest = input_hash(prompt, variables)
        self.calls.append(FakeLLMCall(prompt, dict(variables), digest, language, call_context, structured))
        script = self._next(prompt, digest)
        if isinstance(script, ScriptedError):
            raise script.error()
        return script

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
        _check_limits(max_output_tokens, temperature)
        script = self._call(prompt, variables, language, call_context, structured=True)
        if isinstance(script.output, str):
            raise LlmInvalidOutputError("a structured call needs a mapping output")
        try:
            value = output_model.model_validate(script.output)
        except ValidationError as error:
            raise LlmInvalidOutputError() from error
        return StructuredGeneration(
            value=value,
            usage=script.usage,
            latency_ms=script.latency_ms,
            model_id=script.model_id,
            prompt=prompt,
            repaired=script.repaired,
            cost_usd=script.cost_usd,
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
        _check_limits(max_output_tokens, temperature)
        script = self._call(prompt, variables, language, call_context, structured=False)
        if not isinstance(script.output, str):
            raise LlmInvalidOutputError("a text call needs a string output")
        return TextGeneration(
            text=script.output,
            usage=script.usage,
            latency_ms=script.latency_ms,
            model_id=script.model_id,
            prompt=prompt,
            cost_usd=script.cost_usd,
        )


def _check_limits(max_output_tokens: int, temperature: float) -> None:
    if max_output_tokens <= 0:
        raise ValueError("max_output_tokens must be positive")
    if not 0.0 <= temperature <= 2.0:
        raise ValueError("temperature must be between 0 and 2")


def scripted_calls(fake: FakeLLM, prompt: PromptRef) -> Sequence[FakeLLMCall]:
    """The recorded calls for one prompt, in order."""
    return [call for call in fake.calls if call.prompt == prompt]
