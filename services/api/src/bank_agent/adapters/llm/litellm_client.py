"""LiteLLM behind the ``LLMClient`` port (ADR 0013).

LiteLLM is an optional extra (``uv sync --all-packages --extra litellm``): it is imported lazily on the first
call, so nothing else in the process depends on it. Every call passes its model, key, timeout, and limits
explicitly, with LiteLLM's own retries off (``num_retries=0``); the gateway's decorators own retries, timeouts,
fallback, and cost. The adapter uses LiteLLM's bundled model map (``LITELLM_LOCAL_MODEL_COST_MAP``) so importing
it never fetches anything, and it registers no callbacks.

Provider failures map to the LLM error family by HTTP status: 408 and 504 or a timeout class become
``LlmTimeoutError``, 429 ``LlmRateLimitedError``, any other 4xx ``LlmProviderRejectedError`` (not retried), and
everything else ``LlmProviderError``. The provider exception is not chained, because its text may quote the
request; the message keeps only the exception class and status.
"""

import os
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pydantic import SecretStr

from bank_agent.adapters.llm.client import CompletionRequest, PromptedLLMClient, RawCompletion
from bank_agent.domain.errors import (
    LlmError,
    LlmInvalidOutputError,
    LlmProviderError,
    LlmProviderRejectedError,
    LlmRateLimitedError,
    LlmTimeoutError,
)
from bank_agent.domain.intelligence import TokenUsage
from bank_agent.ports.prompts import PromptRegistry

AsyncCompletion = Callable[..., Awaitable[Any]]


def load_litellm_completion() -> AsyncCompletion:
    """Import LiteLLM with its bundled model map and return ``litellm.acompletion``."""
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    try:
        import litellm  # optional extra, imported on first use
    except ImportError:
        raise LlmProviderRejectedError("the litellm extra is not installed") from None
    litellm.telemetry = False
    completion: AsyncCompletion = litellm.acompletion
    return completion


def map_provider_error(error: Exception) -> LlmError:
    """Translate a provider or LiteLLM exception into the LLM error family."""
    status = getattr(error, "status_code", None)
    name = type(error).__name__
    detail = f"provider call failed: {name}" + (f" (status {status})" if isinstance(status, int) else "")
    if isinstance(error, TimeoutError) or "Timeout" in name or status in (408, 504):
        return LlmTimeoutError(detail)
    if status == 429 or "RateLimit" in name:
        return LlmRateLimitedError(detail)
    if isinstance(status, int) and 400 <= status < 500:
        return LlmProviderRejectedError(detail)
    return LlmProviderError(detail)


def _usage(response: Any) -> TokenUsage:
    usage = getattr(response, "usage", None)
    return TokenUsage(
        input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
    )


def _text(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        raise LlmInvalidOutputError("the provider response has no message") from None
    if not isinstance(content, str):
        raise LlmInvalidOutputError("the provider response has no text content")
    return content


class LiteLLMCompletion:
    """One chat completion through ``litellm.acompletion`` for one configured model."""

    def __init__(
        self,
        model: str,
        *,
        api_key: SecretStr | None,
        timeout_seconds: float,
        acompletion: AsyncCompletion | None = None,
    ) -> None:
        if not model:
            raise LlmProviderRejectedError("no model is configured")
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._acompletion = acompletion

    @property
    def model_id(self) -> str:
        return self._model

    def _arguments(self, request: CompletionRequest) -> Mapping[str, Any]:
        arguments: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": message.role, "content": message.content} for message in request.messages],
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "timeout": self._timeout_seconds,
            "num_retries": 0,
        }
        if self._api_key is not None:
            arguments["api_key"] = self._api_key.get_secret_value()
        if request.json_schema is not None:
            arguments["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": request.schema_name or "output", "schema": dict(request.json_schema)},
            }
        return arguments

    async def complete(self, request: CompletionRequest) -> RawCompletion:
        acompletion = self._acompletion or load_litellm_completion()
        try:
            response = await acompletion(**self._arguments(request))
        except LlmError:
            raise
        except Exception as error:  # every provider failure becomes a typed LLM error
            raise map_provider_error(error) from None
        # The configured id is reported, not the provider's echo, so prices and cassettes key on one name.
        return RawCompletion(text=_text(response), usage=_usage(response), model_id=self._model)


class LiteLLMClient(PromptedLLMClient):
    """The ``LLMClient`` for a live provider: prompts from the registry, completions through LiteLLM."""

    def __init__(
        self,
        registry: PromptRegistry,
        *,
        model: str,
        api_key: SecretStr | None,
        timeout_seconds: float,
        acompletion: AsyncCompletion | None = None,
        monotonic: Callable[[], float] = time.perf_counter,
    ) -> None:
        completion = LiteLLMCompletion(model, api_key=api_key, timeout_seconds=timeout_seconds, acompletion=acompletion)
        super().__init__(registry, completion, monotonic=monotonic)
