import secrets
from datetime import UTC, datetime
from importlib.machinery import ModuleSpec
from pathlib import Path

import pytest

from bank_agent.adapters.llm.budget import BudgetGuardDecorator
from bank_agent.adapters.llm.cassette import CassetteLLM, CassetteMode
from bank_agent.adapters.llm.circuit_breaker import CircuitBreakerDecorator
from bank_agent.adapters.llm.cost import CostAccountingDecorator
from bank_agent.adapters.llm.fallback import FallbackDecorator
from bank_agent.adapters.llm.litellm_client import LiteLLMClient
from bank_agent.adapters.llm.redaction import RedactionDecorator
from bank_agent.adapters.llm.retry import BoundedRetryDecorator
from bank_agent.adapters.llm.timeout import TimeoutDecorator
from bank_agent.adapters.llm.tracing import TracingDecorator
from bank_agent.adapters.llm.unconfigured import UnconfiguredLLMClient
from bank_agent.adapters.prompts.file_registry import FilePromptRegistry
from bank_agent.bootstrap.container import Container
from bank_agent.bootstrap.llm import STACK_ORDER, LlmOverrides, build_llm_client, provider_name
from bank_agent.bootstrap.settings import (
    DEFAULT_CASSETTE_DIR,
    DEFAULT_PRICES_FILE,
    LLMSettings,
    SettingsError,
    load_settings,
)
from bank_agent.domain.errors import ConfigurationError
from bank_agent.ports.llm import LLMClient
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.fake_llm import FakeLLM
from bank_agent.testing.telemetry import RecordingTelemetry

REGISTRY = FilePromptRegistry.from_package()
CLOCK = FixedClock(datetime(2026, 9, 26, tzinfo=UTC))


def _chain(client: LLMClient) -> list[object]:
    """Every layer from the outermost decorator down to the primary provider."""
    layers: list[object] = []
    current: object = client
    while True:
        layers.append(current)
        inner = getattr(current, "inner", None)
        if inner is None or isinstance(current, CassetteLLM):
            return layers
        current = inner


def _build(settings: LLMSettings, overrides: LlmOverrides | None = None, spec: bool = True) -> LLMClient:
    return build_llm_client(
        settings,
        registry=REGISTRY,
        clock=CLOCK,
        telemetry=RecordingTelemetry(),
        overrides=overrides,
        find_spec=lambda name: ModuleSpec(name, None) if spec else None,
    )


def _key() -> str:
    return secrets.token_urlsafe(32)


def test_stack_order_matches_the_documented_order_with_a_fallback() -> None:
    primary, fallback = FakeLLM(), FakeLLM()

    client = _build(LLMSettings(), LlmOverrides(primary=primary, fallback=fallback))

    layers = _chain(client)
    assert [type(layer) for layer in layers[:-1]] == list(STACK_ORDER)
    assert layers[-1] is primary
    fallback_decorator = layers[4]
    assert isinstance(fallback_decorator, FallbackDecorator)
    fallback_layers = _chain(fallback_decorator.fallback)
    assert [type(layer) for layer in fallback_layers[:-1]] == [
        CircuitBreakerDecorator,
        BoundedRetryDecorator,
        TimeoutDecorator,
    ]
    assert fallback_layers[-1] is fallback


def test_stack_order_without_a_fallback_omits_only_the_fallback_decorator() -> None:
    primary = FakeLLM()

    layers = _chain(_build(LLMSettings(), LlmOverrides(primary=primary)))

    assert [type(layer) for layer in layers[:-1]] == [kind for kind in STACK_ORDER if kind is not FallbackDecorator]
    assert STACK_ORDER[:3] == (RedactionDecorator, BudgetGuardDecorator, TracingDecorator)
    assert STACK_ORDER[3] is CostAccountingDecorator


def test_fake_provider_without_an_injected_client_refuses_calls() -> None:
    layers = _chain(_build(LLMSettings()))

    assert isinstance(layers[-1], UnconfiguredLLMClient)
    assert not any(isinstance(layer, FallbackDecorator) for layer in layers)


def test_fake_provider_ignores_a_configured_fallback_model() -> None:
    layers = _chain(_build(LLMSettings(fallback_model="openai/gpt-5-mini")))

    assert not any(isinstance(layer, FallbackDecorator) for layer in layers)


def test_settings_drive_the_reliability_and_budget_parameters() -> None:
    settings = LLMSettings(
        timeout_seconds=7,
        max_retries=1,
        retry_base_delay_seconds=0.25,
        retry_max_delay_seconds=0.1,
        circuit_failure_threshold=3,
        circuit_reset_seconds=12,
        circuit_half_open_max_calls=2,
        session_token_limit=999,
        trace_content=True,
        primary_model="anthropic/claude-sonnet-5",
    )

    layers = _chain(_build(settings, LlmOverrides(primary=FakeLLM())))

    redaction, budget, tracing, _cost, breaker, retry, timeout = layers[:-1]
    assert isinstance(budget, BudgetGuardDecorator)
    assert budget.limits.session_token_limit == 999
    assert budget.model_ids == ("anthropic/claude-sonnet-5",)
    assert isinstance(tracing, TracingDecorator)
    assert tracing.capture_content
    assert tracing.provider_name == "anthropic"
    assert isinstance(breaker, CircuitBreakerDecorator)
    assert (breaker.failure_threshold, breaker.half_open_max_calls) == (3, 2)
    assert breaker.reset_after.total_seconds() == 12
    assert isinstance(retry, BoundedRetryDecorator)
    assert (retry.max_retries, retry.base_delay_seconds, retry.max_delay_seconds) == (1, 0.25, 0.25)
    assert isinstance(timeout, TimeoutDecorator)
    assert timeout.seconds == 7
    assert isinstance(redaction, RedactionDecorator)


def test_litellm_provider_builds_primary_and_fallback_clients() -> None:
    settings = LLMSettings(
        provider="litellm",
        primary_model="anthropic/claude-sonnet-5",
        fallback_model="openai/gpt-5-mini",
        api_key_primary=_key(),  # type: ignore[arg-type]
        api_key_fallback=_key(),  # type: ignore[arg-type]
    )

    layers = _chain(_build(settings))

    assert isinstance(layers[-1], LiteLLMClient)
    assert layers[-1].model_id == "anthropic/claude-sonnet-5"
    fallback = next(layer for layer in layers if isinstance(layer, FallbackDecorator))
    assert isinstance(_chain(fallback.fallback)[-1], LiteLLMClient)
    budget = next(layer for layer in layers if isinstance(layer, BudgetGuardDecorator))
    assert budget.model_ids == ("anthropic/claude-sonnet-5", "openai/gpt-5-mini")


@pytest.mark.parametrize(
    ("settings", "spec", "message"),
    [
        (LLMSettings(provider="litellm", primary_model="a/b"), False, "litellm extra"),
        (LLMSettings(provider="litellm"), True, "LLM_PRIMARY_MODEL"),
        (LLMSettings(provider="litellm", primary_model="a/b"), True, "no API key"),
        (LLMSettings(provider="cassette"), True, "LLM_PRIMARY_MODEL"),
        (LLMSettings(provider="cassette", primary_model="a/b", cassette_mode="record"), True, "no API key"),
    ],
)
def test_refuses_incomplete_provider_configuration(settings: LLMSettings, spec: bool, message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        _build(settings, spec=spec)


def test_cassette_provider_replays_by_default_and_records_through_litellm_when_asked(tmp_path: Path) -> None:
    replay = _chain(
        _build(LLMSettings(provider="cassette", primary_model="fixture/hand-authored", cassette_dir=tmp_path))
    )
    record = _chain(
        _build(
            LLMSettings(
                provider="cassette",
                primary_model="anthropic/claude-sonnet-5",
                cassette_mode="record",
                cassette_dir=tmp_path,
                api_key_primary=_key(),  # type: ignore[arg-type]
            )
        )
    )

    assert isinstance(replay[-1], CassetteLLM)
    assert replay[-1].mode is CassetteMode.REPLAY
    assert replay[-1].inner is None
    assert replay[-1].directory == tmp_path
    assert isinstance(record[-1], CassetteLLM)
    assert record[-1].mode is CassetteMode.RECORD
    assert isinstance(record[-1].inner, LiteLLMClient)


def test_provider_name_reads_the_model_prefix() -> None:
    assert provider_name("anthropic/claude-sonnet-5") == "anthropic"
    assert provider_name("claude-sonnet-5") == "unknown"


def test_defaults_point_at_the_repository_files(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PRICES_FILE", "")
    monkeypatch.setenv("LLM_CASSETTE_DIR", " ")

    settings = load_settings(env_file=None).llm

    assert settings.prices_file == DEFAULT_PRICES_FILE
    assert settings.cassette_dir == DEFAULT_CASSETTE_DIR
    assert DEFAULT_PRICES_FILE.is_file()
    assert DEFAULT_CASSETTE_DIR.is_dir()


@pytest.mark.parametrize(
    ("variable", "value", "problem"),
    [
        ("LLM_TRACE_CONTENT", "true", "LLM_TRACE_CONTENT must be false in production"),
        ("LLM_CASSETTE_MODE", "record", "LLM_CASSETTE_MODE=record is not allowed in production"),
    ],
)
def test_production_refuses_content_capture_and_recording(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str, problem: str
) -> None:
    for name in ("SESSION_SECRET", "CSRF_SECRET", "POSTGRES_APP_PASSWORD"):
        monkeypatch.setenv(name, _key())
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "postgres")
    monkeypatch.setenv("RETRIEVAL_INDEX_SOURCE", "stored")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://bank.example")
    monkeypatch.setenv("LLM_PROVIDER", "cassette")
    monkeypatch.setenv(variable, value)

    with pytest.raises(SettingsError) as raised:
        load_settings(env_file=None)

    assert raised.value.problems == [problem]


def test_container_exposes_the_registry_and_the_gateway() -> None:
    fake = FakeLLM()
    telemetry = RecordingTelemetry()

    container = Container(
        load_settings(env_file=None), clock=CLOCK, telemetry=telemetry, llm_overrides=LlmOverrides(primary=fake)
    )

    assert isinstance(container.llm_client, RedactionDecorator)
    assert _chain(container.llm_client)[-1] is fake
    assert len(container.prompt_registry.get(REGISTRY.refs[0]).body) > 0
    assert container.clock is CLOCK
    assert container.telemetry is telemetry


def test_container_defaults_to_the_unconfigured_client() -> None:
    container = Container(load_settings(env_file=None))

    assert isinstance(_chain(container.llm_client)[-1], UnconfiguredLLMClient)


def test_a_local_ollama_model_needs_no_key_and_gets_the_base_url() -> None:
    settings = LLMSettings(
        provider="litellm", primary_model="ollama/qwen2.5:7b-instruct", api_base="http://localhost:11434"
    )

    provider = _chain(_build(settings))[-1]

    assert isinstance(provider, LiteLLMClient)
    assert provider.model_id == "ollama/qwen2.5:7b-instruct"


def test_a_hosted_model_without_a_key_is_still_refused() -> None:
    with pytest.raises(ConfigurationError, match="no API key"):
        _build(LLMSettings(provider="litellm", primary_model="openai/gpt-5-mini", api_base="https://example.test"))
