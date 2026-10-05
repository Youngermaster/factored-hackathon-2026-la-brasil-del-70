"""One structured call per configured model and language: the operator's check before and after a model change.

``bank-agent llm-probe`` (``deploy/prod.sh llm-probe`` runs it in a throwaway API container with the staged keys and
the server env file) sends a fixed synthetic message, never customer data, to each configured model with the real
``detect_escalation_signals`` prompt and output model, once in Spanish and once in Portuguese. Each line reports
whether the structured reply validated, the error code when it did not, and the latency. Nothing prints a key, a
prompt, or a reply.

The calls go to each provider client directly, without the fallback, retry, circuit breaker, or budget decorators: a
fallback would hide a failing primary, a retry would hide a flaky one, and the four calls cost a fixed fraction of a
cent that the budget ledger does not need to hold.
"""

import importlib.util
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from pydantic import SecretStr

from bank_agent.bootstrap.llm import FindSpec, litellm_provider
from bank_agent.bootstrap.settings import LLMSettings
from bank_agent.domain.errors import ConfigurationError, LlmError
from bank_agent.domain.identifiers import ConversationId, LineageId
from bank_agent.domain.intelligence import LlmCallContext, PromptRef
from bank_agent.domain.llm_outputs import EscalationSignals
from bank_agent.domain.locale import Language
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.prompts import PromptRegistry

PROBE_PROMPT: Final = PromptRef(prompt_id="detect_escalation_signals", version=2)
PROBE_MESSAGES: Final = (
    (Language.ES, "es-MX", "Hola, quiero consultar el saldo de mi cuenta de ahorros."),
    (Language.PT, "pt-BR", "Olá, quero consultar o saldo da minha conta poupança."),
)
"""Fixed synthetic messages with no personal data; each should come back with every signal false."""
PROBE_MAX_OUTPUT_TOKENS: Final = 200
PROBE_CONTEXT: Final = LlmCallContext(
    lineage_id=LineageId("lin-llm-probe"), conversation_id=ConversationId("conv-llm-probe")
)
OK: Final = "ok"

BuildClient = Callable[[str, SecretStr | None], LLMClient]
"""Builds the provider client for one model id and its key; raises ``ConfigurationError`` when it cannot."""


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """One call: which model, in which language, and how it ended (``ok`` or an error code)."""

    role: str
    model: str
    language: Language
    detail: str
    latency_ms: int

    @property
    def ok(self) -> bool:
        return self.detail == OK


def configured_models(settings: LLMSettings) -> list[tuple[str, str, SecretStr | None]]:
    """The primary and, when set, the fallback model with their keys; refuses a configuration with no live model."""
    if settings.provider != "litellm" or not settings.primary_model:
        raise ConfigurationError("llm-probe needs LLM_PROVIDER=litellm and LLM_PRIMARY_MODEL")
    models = [("primary", settings.primary_model, settings.api_key_primary)]
    if settings.fallback_model:
        models.append(("fallback", settings.fallback_model, settings.api_key_fallback))
    return models


async def probe(
    settings: LLMSettings, build: BuildClient, *, monotonic: Callable[[], float] = time.perf_counter
) -> list[ProbeResult]:
    """Call every configured model once per probe language, in order, and report each outcome."""
    results: list[ProbeResult] = []
    for role, model, key in configured_models(settings):
        try:
            client = build(model, key)
        except ConfigurationError:
            results.extend(ProbeResult(role, model, language, "not_configured", 0) for language, *_ in PROBE_MESSAGES)
            continue
        for language, dialect, message in PROBE_MESSAGES:
            started = monotonic()
            detail = OK
            try:
                await client.generate_structured(
                    PROBE_PROMPT,
                    {"customer_message": message, "dialect_hint": dialect},
                    EscalationSignals,
                    language=language,
                    max_output_tokens=PROBE_MAX_OUTPUT_TOKENS,
                    temperature=0.0,
                    call_context=PROBE_CONTEXT,
                )
            except LlmError as error:
                detail = error.code
            results.append(ProbeResult(role, model, language, detail, round((monotonic() - started) * 1000)))
    return results


def litellm_builder(
    settings: LLMSettings, registry: PromptRegistry, find_spec: FindSpec = importlib.util.find_spec
) -> BuildClient:
    """The same provider client the gateway builds for a model: its key, base URL, API version, and timeout."""

    def build(model: str, key: SecretStr | None) -> LLMClient:
        return litellm_provider(settings, registry, model, key, find_spec)

    return build


def report(results: Sequence[ProbeResult]) -> list[str]:
    """One line per call, then the count; model ids and error codes only."""
    lines = [f"llm-probe: {r.role} {r.model} {r.language.value}: {r.detail} ({r.latency_ms} ms)" for r in results]
    passed = sum(r.ok for r in results)
    lines.append(f"llm-probe: {passed} of {len(results)} calls returned a valid structured reply")
    return lines
