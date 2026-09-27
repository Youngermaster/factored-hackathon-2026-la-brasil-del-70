"""The LiteLLM adapter with an injected completion function: no network, and litellm is not installed."""

import builtins
import importlib.util
import json
import os
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from bank_agent.adapters.llm import litellm_client
from bank_agent.adapters.llm.client import ChatMessage, CompletionRequest
from bank_agent.adapters.llm.litellm_client import LiteLLMClient, LiteLLMCompletion, map_provider_error
from bank_agent.adapters.llm.unconfigured import UnconfiguredLLMClient
from bank_agent.adapters.prompts.file_registry import FilePromptRegistry
from bank_agent.domain.errors import (
    LlmInvalidOutputError,
    LlmProviderError,
    LlmProviderRejectedError,
    LlmRateLimitedError,
    LlmTimeoutError,
)
from bank_agent.domain.llm_outputs import EscalationSignals
from bank_agent.domain.locale import Language
from bank_agent_llm import CONTEXT, DISPUTE_PROMPT, SIGNALS_PROMPT, dispute_variables

REQUEST = CompletionRequest(
    messages=(ChatMessage("system", "rules"), ChatMessage("user", "hola")),
    max_output_tokens=300,
    temperature=0.1,
    json_schema={"type": "object"},
    schema_name="EscalationSignals",
)


def _response(content: object, prompt_tokens: int | None = 12, completion_tokens: int | None = 7) -> SimpleNamespace:
    return SimpleNamespace(
        model="claude-sonnet-5",
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


class Recorder:
    def __init__(self, result: object) -> None:
        self.result = result
        self.kwargs: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> object:
        self.kwargs.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


async def test_sends_explicit_per_call_arguments_and_reports_the_configured_model() -> None:
    recorder = Recorder(_response('{"ok": true}'))
    completion = LiteLLMCompletion(
        "anthropic/claude-sonnet-5", api_key=SecretStr("k" * 40), timeout_seconds=12.5, acompletion=recorder
    )

    raw = await completion.complete(REQUEST)

    (kwargs,) = recorder.kwargs
    assert kwargs["model"] == "anthropic/claude-sonnet-5"
    assert kwargs["messages"] == [{"role": "system", "content": "rules"}, {"role": "user", "content": "hola"}]
    assert kwargs["max_tokens"] == 300
    assert kwargs["temperature"] == 0.1
    assert kwargs["timeout"] == 12.5
    assert kwargs["num_retries"] == 0
    assert kwargs["api_key"] == "k" * 40
    assert kwargs["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "EscalationSignals", "schema": {"type": "object"}},
    }
    assert raw.text == '{"ok": true}'
    assert raw.usage.input_tokens == 12
    assert raw.usage.output_tokens == 7
    assert raw.model_id == "anthropic/claude-sonnet-5"
    assert completion.model_id == "anthropic/claude-sonnet-5"


async def test_omits_the_key_and_schema_when_absent_and_tolerates_missing_usage() -> None:
    recorder = Recorder(_response("hola", prompt_tokens=None, completion_tokens=None))
    completion = LiteLLMCompletion("openai/gpt-5-mini", api_key=None, timeout_seconds=5, acompletion=recorder)

    raw = await completion.complete(CompletionRequest(REQUEST.messages, 50, 0.0))

    assert "api_key" not in recorder.kwargs[0]
    assert "response_format" not in recorder.kwargs[0]
    assert raw.usage.input_tokens == 0


@pytest.mark.parametrize("response", [_response(None), SimpleNamespace(choices=[]), object()])
async def test_a_response_without_text_is_invalid_output(response: object) -> None:
    completion = LiteLLMCompletion("m/x", api_key=None, timeout_seconds=5, acompletion=Recorder(response))

    with pytest.raises(LlmInvalidOutputError):
        await completion.complete(REQUEST)


class ProviderFailureError(Exception):
    def __init__(self, status_code: int | None, text: str = "prompt text that must not leak") -> None:
        super().__init__(text)
        self.status_code = status_code


class Timeout(Exception):  # noqa: N818  (mirrors the LiteLLM class name the mapping recognizes)
    pass


class RateLimitError(Exception):
    pass


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError(), LlmTimeoutError),
        (Timeout(), LlmTimeoutError),
        (ProviderFailureError(408), LlmTimeoutError),
        (ProviderFailureError(504), LlmTimeoutError),
        (ProviderFailureError(429), LlmRateLimitedError),
        (RateLimitError(), LlmRateLimitedError),
        (ProviderFailureError(400), LlmProviderRejectedError),
        (ProviderFailureError(401), LlmProviderRejectedError),
        (ProviderFailureError(404), LlmProviderRejectedError),
        (ProviderFailureError(500), LlmProviderError),
        (ProviderFailureError(503), LlmProviderError),
        (ProviderFailureError(None), LlmProviderError),
        (ConnectionError(), LlmProviderError),
    ],
)
def test_maps_provider_failures_to_typed_errors(error: Exception, expected: type[Exception]) -> None:
    mapped = map_provider_error(error)

    assert type(mapped) is expected


async def test_provider_failures_are_not_chained_and_do_not_leak_text() -> None:
    completion = LiteLLMCompletion(
        "m/x", api_key=None, timeout_seconds=5, acompletion=Recorder(ProviderFailureError(503))
    )

    with pytest.raises(LlmProviderError) as raised:
        await completion.complete(REQUEST)

    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__
    assert "must not leak" not in str(raised.value)
    assert "ProviderFailureError (status 503)" in str(raised.value)


async def test_typed_llm_errors_pass_through_unchanged() -> None:
    completion = LiteLLMCompletion("m/x", api_key=None, timeout_seconds=5, acompletion=Recorder(LlmRateLimitedError()))

    with pytest.raises(LlmRateLimitedError):
        await completion.complete(REQUEST)


def test_refuses_an_empty_model() -> None:
    with pytest.raises(LlmProviderRejectedError, match="no model"):
        LiteLLMCompletion("", api_key=None, timeout_seconds=5)


async def test_client_runs_prompts_through_litellm() -> None:
    reply = json.dumps(
        {
            "legal_or_regulator_mention": True,
            "distress": False,
            "human_requested": False,
            "third_party_admission": False,
        }
    )
    recorder = Recorder(_response(reply))
    client = LiteLLMClient(
        FilePromptRegistry.from_package(),
        model="anthropic/claude-haiku-4-5-20251001",
        api_key=None,
        timeout_seconds=5,
        acompletion=recorder,
    )

    result = await client.generate_structured(
        SIGNALS_PROMPT,
        {"customer_message": "Voy a poner una queja en CONDUSEF"},
        EscalationSignals,
        language=Language.ES,
        max_output_tokens=100,
        temperature=0.0,
        call_context=CONTEXT,
    )

    assert result.value.legal_or_regulator_mention
    assert result.model_id == "anthropic/claude-haiku-4-5-20251001"
    assert recorder.kwargs[0]["response_format"]["json_schema"]["name"] == "EscalationSignals"


def test_the_litellm_extra_is_not_installed_in_the_development_environment() -> None:
    assert importlib.util.find_spec("litellm") is None


def test_loading_litellm_without_the_extra_raises_a_typed_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def refuse(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "litellm":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "False")  # restored after the test

    with pytest.raises(LlmProviderRejectedError, match="litellm extra is not installed"):
        litellm_client.load_litellm_completion()


def test_loading_litellm_uses_the_local_model_map_and_disables_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(telemetry=True, acompletion=Recorder(None))
    monkeypatch.setitem(sys.modules, "litellm", fake)
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "False")  # restored after the test

    completion = litellm_client.load_litellm_completion()

    assert completion is fake.acompletion
    assert fake.telemetry is False
    assert os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] == "True"


async def test_unconfigured_client_refuses_every_call() -> None:
    client = UnconfiguredLLMClient()

    with pytest.raises(LlmProviderRejectedError, match="no language model provider"):
        await client.generate_structured(
            DISPUTE_PROMPT,
            dispute_variables(),
            EscalationSignals,
            language=Language.ES,
            max_output_tokens=10,
            temperature=0.0,
            call_context=CONTEXT,
        )
    with pytest.raises(LlmProviderRejectedError):
        await client.generate_text(
            DISPUTE_PROMPT,
            dispute_variables(),
            language=Language.ES,
            max_output_tokens=10,
            temperature=0.0,
            call_context=CONTEXT,
        )
    assert not LlmProviderRejectedError.retryable


async def test_passes_the_configured_base_url_for_a_local_provider() -> None:
    recorder = Recorder(_response("hola"))
    completion = LiteLLMCompletion(
        "ollama/qwen2.5:7b-instruct", api_key=None, timeout_seconds=5, acompletion=recorder,
        api_base="http://localhost:11434",
    )  # fmt: skip

    await completion.complete(CompletionRequest(REQUEST.messages, 50, 0.0))

    assert recorder.kwargs[0]["api_base"] == "http://localhost:11434"
    assert "api_key" not in recorder.kwargs[0]
