"""One language model call as a value, and the base class every decorator shares.

A decorator implements the ``LLMClient`` port by turning either port method into an ``LlmRequest``, running
its own behavior around the call in ``around``, and passing the request on to ``inner``. Structured and text
calls therefore go through the same code path in every decorator, and each decorator is written once.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any, cast

from pydantic import BaseModel

from bank_agent.domain.intelligence import (
    LlmCallContext,
    PromptRef,
    PromptValue,
    StructuredGeneration,
    TextGeneration,
)
from bank_agent.domain.locale import Language
from bank_agent.ports.llm import LLMClient

Generation = StructuredGeneration[Any] | TextGeneration
Proceed = Callable[["LlmRequest"], Awaitable[Generation]]


@dataclass(frozen=True, slots=True)
class LlmRequest:
    """The arguments of one port call. ``output_model`` is ``None`` for a text call."""

    prompt: PromptRef
    variables: Mapping[str, PromptValue]
    output_model: type[BaseModel] | None
    language: Language
    max_output_tokens: int
    temperature: float
    call_context: LlmCallContext

    @property
    def structured(self) -> bool:
        return self.output_model is not None

    def with_variables(self, variables: Mapping[str, PromptValue]) -> "LlmRequest":
        return replace(self, variables=variables)


async def dispatch(client: LLMClient, request: LlmRequest) -> Generation:
    """Send ``request`` to ``client`` through the matching port method."""
    if request.output_model is None:
        return await client.generate_text(
            request.prompt,
            request.variables,
            language=request.language,
            max_output_tokens=request.max_output_tokens,
            temperature=request.temperature,
            call_context=request.call_context,
        )
    return await client.generate_structured(
        request.prompt,
        request.variables,
        request.output_model,
        language=request.language,
        max_output_tokens=request.max_output_tokens,
        temperature=request.temperature,
        call_context=request.call_context,
    )


class LlmDecorator(ABC):
    """Base for decorators that wrap one ``LLMClient`` and implement the same port."""

    def __init__(self, inner: LLMClient) -> None:
        self.inner = inner

    @abstractmethod
    async def around(self, request: LlmRequest, proceed: Proceed) -> Generation:
        """Run the decorator's behavior; call ``proceed`` to continue with the inner client."""

    async def _proceed(self, request: LlmRequest) -> Generation:
        return await dispatch(self.inner, request)

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
        request = LlmRequest(prompt, variables, output_model, language, max_output_tokens, temperature, call_context)
        return cast(StructuredGeneration[OutputT], await self.around(request, self._proceed))

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
        request = LlmRequest(prompt, variables, None, language, max_output_tokens, temperature, call_context)
        result = await self.around(request, self._proceed)
        if not isinstance(result, TextGeneration):
            raise TypeError("a text call returned a structured result")
        return result
