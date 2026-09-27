"""Builds the language model gateway from settings: the provider and the decorator stack.

Order, outermost first (``docs/architecture/llm-gateway.md``):

1. ``RedactionDecorator``: nothing below it sees unredacted variables.
2. ``BudgetGuardDecorator``: refuses before anything is spent or traced.
3. ``TracingDecorator``: one span per logical call, including its cost.
4. ``CostAccountingDecorator``: prices the reply, so tracing and the budget see the cost.
5. ``FallbackDecorator`` (only with a fallback model): primary stack, then fallback stack.
6. Per provider: ``CircuitBreakerDecorator``, ``BoundedRetryDecorator``, ``TimeoutDecorator``, then the provider.

This keeps the order the phase prompt names (redaction, budget, tracing, circuit breaker, retry, timeout,
provider) and places cost accounting and fallback, which it does not order.
"""

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from importlib.machinery import ModuleSpec
from typing import Final

from pydantic import SecretStr

from bank_agent.adapters.llm.budget import BudgetGuardDecorator, BudgetLimits
from bank_agent.adapters.llm.cassette import CassetteLLM, CassetteMode
from bank_agent.adapters.llm.circuit_breaker import CircuitBreakerDecorator
from bank_agent.adapters.llm.cost import CostAccountingDecorator
from bank_agent.adapters.llm.fallback import FallbackDecorator
from bank_agent.adapters.llm.litellm_client import LiteLLMClient
from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.adapters.llm.redaction import RedactionDecorator, Redactor
from bank_agent.adapters.llm.retry import BoundedRetryDecorator, Sleep
from bank_agent.adapters.llm.timeout import TimeoutDecorator
from bank_agent.adapters.llm.tracing import TracingDecorator
from bank_agent.adapters.llm.unconfigured import UnconfiguredLLMClient
from bank_agent.bootstrap.settings import LLMSettings
from bank_agent.domain.errors import ConfigurationError
from bank_agent.ports.determinism import Clock
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.prompts import PromptRegistry
from bank_agent.ports.telemetry import Telemetry

STACK_ORDER: Final = (
    RedactionDecorator,
    BudgetGuardDecorator,
    TracingDecorator,
    CostAccountingDecorator,
    FallbackDecorator,
    CircuitBreakerDecorator,
    BoundedRetryDecorator,
    TimeoutDecorator,
)
"""The documented decorator order, outermost first; ``FallbackDecorator`` is present only with a fallback."""

FindSpec = Callable[[str], ModuleSpec | None]


@dataclass(frozen=True, slots=True)
class LlmOverrides:
    """Clients injected instead of the configured providers (tests and the evaluation harness), and the sleep
    function the retry decorator uses (tests pass one that does not wait)."""

    primary: LLMClient | None = None
    fallback: LLMClient | None = None
    sleep: Sleep | None = None


def _model_id(client: LLMClient, configured: str, provider: str) -> str:
    declared = getattr(client, "model_id", None)
    if isinstance(declared, str) and declared:
        return declared
    return configured or f"{provider}/unnamed"


def provider_name(model_id: str) -> str:
    """The GenAI ``gen_ai.provider.name`` for a LiteLLM-style ``provider/model`` id."""
    head, separator, _ = model_id.partition("/")
    return head if separator else "unknown"


def _litellm(
    settings: LLMSettings, registry: PromptRegistry, model: str, key: SecretStr | None, find_spec: FindSpec
) -> LiteLLMClient:
    if find_spec("litellm") is None:
        raise ConfigurationError("LLM_PROVIDER=litellm needs the litellm extra: uv sync --all-packages --extra litellm")
    if not model:
        raise ConfigurationError("LLM_PROVIDER=litellm needs LLM_PRIMARY_MODEL (and a key for every model)")
    if key is None or not key.get_secret_value().strip():
        raise ConfigurationError(f"the model {model} has no API key configured")
    return LiteLLMClient(registry, model=model, api_key=key, timeout_seconds=settings.timeout_seconds)


def _provider(
    settings: LLMSettings,
    *,
    model: str,
    key: SecretStr | None,
    registry: PromptRegistry,
    redactor: Redactor,
    clock: Clock,
    find_spec: FindSpec,
) -> LLMClient:
    if settings.provider == "litellm":
        return _litellm(settings, registry, model, key, find_spec)
    if settings.provider == "cassette":
        if not model:
            raise ConfigurationError("LLM_PROVIDER=cassette needs LLM_PRIMARY_MODEL, the model the cassettes hold")
        mode = CassetteMode(settings.cassette_mode)
        inner = _litellm(settings, registry, model, key, find_spec) if mode is CassetteMode.RECORD else None
        return CassetteLLM(
            settings.cassette_dir, model_id=model, redactor=redactor, clock=clock, mode=mode, inner=inner
        )
    return UnconfiguredLLMClient()


def _reliability(client: LLMClient, settings: LLMSettings, clock: Clock, sleep: Sleep | None) -> LLMClient:
    timed = TimeoutDecorator(client, seconds=settings.timeout_seconds)
    retried = BoundedRetryDecorator(
        timed,
        max_retries=settings.max_retries,
        base_delay_seconds=settings.retry_base_delay_seconds,
        max_delay_seconds=max(settings.retry_max_delay_seconds, settings.retry_base_delay_seconds),
        sleep=sleep,
    )
    return CircuitBreakerDecorator(
        retried,
        clock=clock,
        failure_threshold=settings.circuit_failure_threshold,
        reset_after=timedelta(seconds=settings.circuit_reset_seconds),
        half_open_max_calls=settings.circuit_half_open_max_calls,
    )


def build_llm_client(
    settings: LLMSettings,
    *,
    registry: PromptRegistry,
    clock: Clock,
    telemetry: Telemetry,
    overrides: LlmOverrides | None = None,
    find_spec: FindSpec = importlib.util.find_spec,
) -> LLMClient:
    """Return the fully decorated ``LLMClient`` described by ``settings``."""
    overrides = overrides or LlmOverrides()
    prices = PriceTable.from_yaml(settings.prices_file)
    redactor = Redactor()

    def configured(model: str, key: SecretStr | None) -> LLMClient:
        return _provider(
            settings, model=model, key=key, registry=registry, redactor=redactor, clock=clock, find_spec=find_spec
        )

    primary = overrides.primary or configured(settings.primary_model, settings.api_key_primary)
    primary_model = _model_id(primary, settings.primary_model, settings.provider)
    model_ids = [primary_model]
    client: LLMClient = _reliability(primary, settings, clock, overrides.sleep)

    fallback = overrides.fallback
    if fallback is None and settings.fallback_model and settings.provider != "fake":
        fallback = configured(settings.fallback_model, settings.api_key_fallback)
    if fallback is not None:
        model_ids.append(_model_id(fallback, settings.fallback_model, settings.provider))
        client = FallbackDecorator(client, _reliability(fallback, settings, clock, overrides.sleep))

    client = CostAccountingDecorator(client, prices=prices, telemetry=telemetry)
    client = TracingDecorator(
        client,
        telemetry=telemetry,
        provider_name=provider_name(primary_model),
        request_model=primary_model,
        capture_content=settings.trace_content,
    )
    client = BudgetGuardDecorator(
        client,
        limits=BudgetLimits(
            session_token_limit=settings.session_token_limit,
            conversation_cost_limit_usd=settings.conversation_budget_usd,
            daily_cost_limit_usd=settings.daily_budget_usd,
        ),
        prices=prices,
        model_ids=tuple(model_ids),
        clock=clock,
    )
    return RedactionDecorator(client, redactor=redactor)
