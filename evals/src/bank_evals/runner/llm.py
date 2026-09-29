"""The language model wiring of a run: one gateway, from settings, in one of four modes.

- ``off``: every call is refused (``UnconfiguredLLMClient``). P runs its deterministic fallbacks, B1 cannot act,
  the simulated user plays its scripted fallback turns, and the judge is pending. The model label is ``none``.
- ``replay``: cassettes only. A missing cassette fails that call like a refused call (``LlmProviderRejectedError``,
  so callers take their fallback) and is counted; the report states the cassette coverage.
- ``record``: live calls through LiteLLM with the ``LLM_*`` settings, each reply written as a cassette.
- ``inject``: tests pass a client (``FakeLLM``).

The provider is never hard-coded: the model, the API base, and the keys come from ``LLMSettings``. Every run goes
through ``build_llm_client``, so the redaction, budget, tracing, cost, and reliability decorators apply.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from bank_agent.adapters.llm.cassette import CassetteLLM, CassetteMissingError, CassetteMode
from bank_agent.adapters.llm.litellm_client import LiteLLMClient
from bank_agent.adapters.llm.redaction import Redactor
from bank_agent.adapters.llm.unconfigured import UnconfiguredLLMClient
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.adapters.telemetry.noop import NoopTelemetry
from bank_agent.bootstrap.llm import LlmOverrides, build_llm_client
from bank_agent.bootstrap.settings import LLMSettings
from bank_agent.domain.errors import ConfigurationError, LlmProviderRejectedError
from bank_agent.domain.intelligence import LlmCallContext, PromptRef, PromptValue, StructuredGeneration, TextGeneration
from bank_agent.domain.locale import Language
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.prompts import PromptRegistry

LlmMode = Literal["off", "replay", "record", "inject"]


@dataclass
class CassetteMisses:
    """Calls a replay could not serve, per prompt."""

    by_prompt: Counter[str] = field(default_factory=Counter)

    @property
    def total(self) -> int:
        return sum(self.by_prompt.values())


class MissTolerantCassettes:
    """Implements ``LLMClient``: a replay whose missing cassettes fail like a refused call, and are counted."""

    def __init__(self, inner: CassetteLLM, misses: CassetteMisses) -> None:
        self._inner, self.misses, self.model_id = inner, misses, inner.model_id

    async def generate_structured[OutputT: BaseModel](
        self, prompt: PromptRef, variables: Mapping[str, PromptValue], output_model: type[OutputT], *,
        language: Language, max_output_tokens: int, temperature: float, call_context: LlmCallContext,
    ) -> StructuredGeneration[OutputT]:  # fmt: skip
        try:
            return await self._inner.generate_structured(
                prompt, variables, output_model, language=language, max_output_tokens=max_output_tokens,
                temperature=temperature, call_context=call_context,
            )  # fmt: skip
        except CassetteMissingError:
            self.misses.by_prompt[str(prompt)] += 1
            raise LlmProviderRejectedError(f"no cassette for {prompt}") from None

    async def generate_text(
        self, prompt: PromptRef, variables: Mapping[str, PromptValue], *, language: Language,
        max_output_tokens: int, temperature: float, call_context: LlmCallContext,
    ) -> TextGeneration:  # fmt: skip
        try:
            return await self._inner.generate_text(
                prompt, variables, language=language, max_output_tokens=max_output_tokens,
                temperature=temperature, call_context=call_context,
            )  # fmt: skip
        except CassetteMissingError:
            self.misses.by_prompt[str(prompt)] += 1
            raise LlmProviderRejectedError(f"no cassette for {prompt}") from None


@dataclass
class RunLlm:
    client: LLMClient
    mode: LlmMode
    model_label: str
    misses: CassetteMisses = field(default_factory=CassetteMisses)

    @property
    def available(self) -> bool:
        """Whether a model can answer at all (``off`` refuses everything)."""
        return self.mode != "off"


def model_label(settings: LLMSettings, mode: LlmMode) -> str:
    if mode == "off":
        return "none"
    model = settings.primary_model or "unnamed"
    return f"{model} ({'cassettes' if mode == 'replay' else settings.provider})"


def build_run_llm(
    settings: LLMSettings,
    registry: PromptRegistry,
    mode: LlmMode,
    *,
    cassette_dir: Path | None = None,
    injected: LLMClient | None = None,
    label: str | None = None,
) -> RunLlm:
    """The decorated gateway for a run in ``mode``, with the run's own cassette directory."""
    misses = CassetteMisses()
    directory = cassette_dir or settings.cassette_dir
    primary: Any
    if mode == "inject":
        if injected is None:
            raise ConfigurationError("inject mode needs a client")
        primary = injected
    elif mode == "off":
        primary = UnconfiguredLLMClient()
    else:
        if not settings.primary_model:
            raise ConfigurationError(f"--llm {mode} needs LLM_PRIMARY_MODEL (the model the cassettes hold)")
        inner = None
        if mode == "record":
            inner = LiteLLMClient(
                registry, model=settings.primary_model, api_key=settings.api_key_primary,
                timeout_seconds=settings.timeout_seconds, api_base=settings.api_base or None,
            )  # fmt: skip
        cassettes = CassetteLLM(
            directory, model_id=settings.primary_model, redactor=Redactor(), clock=SystemClock(),
            mode=CassetteMode.RECORD if mode == "record" else CassetteMode.REPLAY, inner=inner,
        )  # fmt: skip
        primary = MissTolerantCassettes(cassettes, misses) if mode == "replay" else cassettes
    client = build_llm_client(
        settings.model_copy(update={"provider": "fake", "fallback_model": ""}),
        registry=registry,
        clock=SystemClock(),
        telemetry=NoopTelemetry(),
        overrides=LlmOverrides(primary=primary),
    )
    return RunLlm(client, mode, label or model_label(settings, mode), misses)
