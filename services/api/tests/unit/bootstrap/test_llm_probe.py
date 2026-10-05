"""The operator's model probe: one structured call per configured model and language, outcomes only."""

from importlib.machinery import ModuleSpec
from itertools import count

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from bank_agent.adapters.llm.litellm_client import LiteLLMClient
from bank_agent.adapters.prompts.file_registry import FilePromptRegistry
from bank_agent.bootstrap.llm_probe import (
    PROBE_MESSAGES,
    PROBE_PROMPT,
    BuildClient,
    configured_models,
    litellm_builder,
    probe,
    report,
)
from bank_agent.bootstrap.settings import LLMSettings
from bank_agent.cli import app
from bank_agent.domain.errors import ConfigurationError, LlmTimeoutError
from bank_agent.domain.locale import Language
from bank_agent.ports.llm import LLMClient
from bank_agent.testing.fake_llm import FakeLLM, ScriptedError, ScriptedResponse

QUIET = {
    "legal_or_regulator_mention": False,
    "distress": False,
    "human_requested": False,
    "third_party_admission": False,
}
AZURE = LLMSettings(
    provider="litellm",
    primary_model="azure/gpt-4.1-mini",
    fallback_model="azure/gpt-4o",
    api_key_primary=SecretStr("fixture-primary-key"),
    api_key_fallback=SecretStr("fixture-fallback-key"),
    api_base="https://example-resource.openai.azure.com/",
    api_version="2024-10-21",
)


def _builder(clients: dict[str, LLMClient]) -> BuildClient:
    def build(model: str, key: SecretStr | None) -> LLMClient:
        return clients[model]

    return build


def _ticks() -> "count[float]":
    return count(0.0, 0.25)


def test_refuses_a_configuration_without_a_live_model() -> None:
    with pytest.raises(ConfigurationError, match="LLM_PROVIDER=litellm"):
        configured_models(LLMSettings(provider="fake"))


def test_only_the_primary_is_probed_when_no_fallback_is_configured() -> None:
    settings = LLMSettings(provider="litellm", primary_model="azure/gpt-4.1-mini")
    assert [(role, model) for role, model, _ in configured_models(settings)] == [("primary", "azure/gpt-4.1-mini")]


async def test_each_model_is_called_once_per_language_and_a_failure_names_its_code() -> None:
    primary, fallback = FakeLLM(), FakeLLM()
    primary.script(PROBE_PROMPT, ScriptedResponse(QUIET))
    fallback.script(PROBE_PROMPT, ScriptedError(LlmTimeoutError))
    ticks = _ticks()

    results = await probe(
        AZURE,
        _builder({"azure/gpt-4.1-mini": primary, "azure/gpt-4o": fallback}),
        monotonic=lambda: next(ticks),
    )

    assert [(r.role, r.model, r.language, r.detail) for r in results] == [
        ("primary", "azure/gpt-4.1-mini", Language.ES, "ok"),
        ("primary", "azure/gpt-4.1-mini", Language.PT, "ok"),
        ("fallback", "azure/gpt-4o", Language.ES, "llm_timeout"),
        ("fallback", "azure/gpt-4o", Language.PT, "llm_timeout"),
    ]
    assert all(r.latency_ms == 250 for r in results)
    sent = [(call.language, call.variables["customer_message"]) for call in primary.calls]
    assert sent == [(language, message) for language, _, message in PROBE_MESSAGES]
    assert {call.prompt for call in primary.calls + fallback.calls} == {PROBE_PROMPT}


async def test_a_model_the_gateway_cannot_build_is_reported_without_a_call() -> None:
    def build(model: str, key: SecretStr | None) -> LLMClient:
        raise ConfigurationError(f"the model {model} has no API key configured")

    results = await probe(LLMSettings(provider="litellm", primary_model="azure/gpt-4.1-mini"), build)

    assert [(r.detail, r.latency_ms) for r in results] == [("not_configured", 0), ("not_configured", 0)]
    assert not any(r.ok for r in results)


def test_the_builder_gives_each_model_its_own_key_base_url_and_api_version() -> None:
    build = litellm_builder(AZURE, FilePromptRegistry.from_package(), find_spec=lambda name: ModuleSpec(name, None))

    client = build("azure/gpt-4o", AZURE.api_key_fallback)

    assert isinstance(client, LiteLLMClient)
    assert client.model_id == "azure/gpt-4o"
    assert client.api_version == "2024-10-21"
    with pytest.raises(ConfigurationError, match="no API key"):
        build("azure/gpt-4.1-mini", None)


async def test_the_report_names_models_and_codes_but_never_the_probe_text() -> None:
    primary = FakeLLM()
    primary.script(PROBE_PROMPT, ScriptedResponse(QUIET))
    settings = LLMSettings(provider="litellm", primary_model="azure/gpt-4.1-mini")

    lines = report(await probe(settings, _builder({"azure/gpt-4.1-mini": primary})))

    assert lines[0].startswith("llm-probe: primary azure/gpt-4.1-mini es: ok")
    assert lines[-1] == "llm-probe: 2 of 2 calls returned a valid structured reply"
    text = "\n".join(lines)
    assert not any(message in text for _, _, message in PROBE_MESSAGES)


def test_the_cli_exits_2_without_a_live_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")

    result = CliRunner().invoke(app, ["llm-probe"])

    assert result.exit_code == 2
    assert "LLM_PROVIDER=litellm" in result.output
