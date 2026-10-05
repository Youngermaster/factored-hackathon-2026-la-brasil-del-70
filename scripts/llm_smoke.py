#!/usr/bin/env python3
"""Run the phase 08 fixture prompt cases against the configured language model provider (opt-in smoke test).

Usage:
    make llm-smoke                                             reads the settings like the other make targets
    uv run --frozen --extra litellm --package bank-agent python scripts/llm_smoke.py [--no-env-file]

It is never part of ``make check`` or CI: it calls a live provider. Every committed fixture cassette under
``evals/cassettes/`` is one case (es and pt, the four workflows' extraction prompts plus phrasing). Each case goes
through the full gateway (redaction, budget, tracing, retries, timeout, then LiteLLM); a structured case passes when
the reply validates against its output model, a text case when a non-empty reply comes back. The table reports each
case with its latency; results are a local development measurement, not an evaluation.

Exit status: 0 when every case passes, 1 when some fail, 2 when the provider is not configured or not reachable.
For a local Ollama model the script checks the server and the pulled model before the first call.

With ``LANGFUSE_ENABLED=true`` (and the settings the API requires for it: ``LLM_PROVIDER=litellm``, the base URL, and
both keys) the gateway's telemetry is the API's own, so every call also goes to Langfuse through the same allowlisting
exporter as the API (one metadata-only generation per call, never prompts or replies), flushed before the script exits.
This checks the export without a database or a running API (docs/operations/observability.md).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from bank_agent.adapters.llm.cassette import Cassette, load_cassette
from bank_agent.adapters.prompts.file_registry import FilePromptRegistry
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.adapters.telemetry.noop import NoopTelemetry
from bank_agent.bootstrap.llm import KEYLESS_PROVIDERS, build_llm_client, provider_name
from bank_agent.bootstrap.observability import build_observability
from bank_agent.bootstrap.settings import AppSettings, LLMSettings, SettingsError, load_settings
from bank_agent.domain import llm_outputs
from bank_agent.domain.errors import ConfigurationError, LlmError
from bank_agent.domain.identifiers import ConversationId, LineageId
from bank_agent.domain.intelligence import LlmCallContext, PromptValue
from bank_agent.ports.llm import LLMClient
from bank_agent.ports.telemetry import Telemetry

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CASSETTE_DIR = REPOSITORY_ROOT / "evals" / "cassettes"
DEFAULT_OLLAMA_BASE = "http://localhost:11434"
MAX_OUTPUT_TOKENS = 600
Fetch = Callable[[str, float], bytes]


class SmokeSetupError(Exception):
    """The provider is not configured or not reachable; the message says what to do."""


@dataclass(frozen=True)
class CaseResult:
    prompt: str
    workflow: str
    case: str
    language: str
    passed: bool
    latency_ms: int
    detail: str


def load_cases(directory: Path = CASSETTE_DIR) -> list[Cassette]:
    """Every committed cassette, ordered by prompt, workflow, case, and language."""
    cases = [load_cassette(path) for path in sorted(directory.glob("*/*/*.json"))]
    return sorted(cases, key=lambda c: (str(c.prompt), c.labels.get("workflow", ""), c.labels.get("case", ""),
                                        c.language.value))  # fmt: skip


def output_model(name: str | None) -> type[BaseModel]:
    model = getattr(llm_outputs, name or "", None)
    if not (isinstance(model, type) and issubclass(model, BaseModel)):
        raise SmokeSetupError(f"unknown output model {name!r} in a fixture cassette")
    return model


def _urlopen(url: str, timeout: float) -> bytes:
    # The URL is the configured provider base (checked to be http or https by check_provider).
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310  # nosec B310
        body: bytes = response.read()
    return body


def check_provider(settings: LLMSettings, fetch: Fetch = _urlopen) -> str:
    """Refuse anything but a configured live provider; for Ollama, check the server and the pulled model."""
    if settings.provider != "litellm" or not settings.primary_model:
        raise SmokeSetupError(
            "set LLM_PROVIDER=litellm and LLM_PRIMARY_MODEL (for example ollama/qwen2.5:7b-instruct); "
            f"the current provider is {settings.provider!r}"
        )
    model = settings.primary_model
    if provider_name(model) not in KEYLESS_PROVIDERS:
        return f"{model} (hosted; reachability is checked by the first call)"
    base = (settings.api_base or DEFAULT_OLLAMA_BASE).rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise SmokeSetupError(f"LLM_API_BASE must be an http(s) URL, got {base!r}")
    try:
        tags = json.loads(fetch(f"{base}/api/tags", 3.0))
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise SmokeSetupError(f"the Ollama server at {base} is not reachable ({type(error).__name__}); "
                              "start it with `ollama serve`") from None  # fmt: skip
    wanted = model.split("/", 1)[1]
    names = {str(item.get("name", "")) for item in tags.get("models", []) if isinstance(item, dict)}
    if wanted not in names:
        raise SmokeSetupError(f"the model {wanted} is not pulled on {base}; run `ollama pull {wanted}`")
    return f"{model} at {base}"


async def run_case(client: LLMClient, cassette: Cassette, index: int) -> CaseResult:
    context = LlmCallContext(
        lineage_id=LineageId(f"lin-smoke-{index:03d}"), conversation_id=ConversationId(f"conv-smoke-{index:03d}")
    )
    variables = cast("Mapping[str, PromptValue]", cassette.variables)
    started = time.perf_counter()
    detail = "ok"
    try:
        if cassette.kind == "structured":
            await client.generate_structured(
                cassette.prompt, variables, output_model(cassette.output_model), language=cassette.language,
                max_output_tokens=MAX_OUTPUT_TOKENS, temperature=0.0, call_context=context,
            )  # fmt: skip
        else:
            reply = await client.generate_text(
                cassette.prompt, variables, language=cassette.language,
                max_output_tokens=MAX_OUTPUT_TOKENS, temperature=0.0, call_context=context,
            )  # fmt: skip
            if not reply.text.strip():
                detail = "empty text"
    except LlmError as error:
        detail = error.code
    latency = int((time.perf_counter() - started) * 1000)
    labels = cassette.labels
    return CaseResult(str(cassette.prompt), labels.get("workflow", "-"), labels.get("case", "-"),
                      cassette.language.value, detail == "ok", latency, detail)  # fmt: skip


def summarize(results: Sequence[CaseResult]) -> str:
    """The pass/fail and latency table, then the pass rate and p50/p95 latency."""
    header = f"{'prompt':34} {'workflow':16} {'case':10} {'lang':4} {'result':22} {'ms':>7}"
    lines = [header, "-" * len(header)]
    for r in results:
        verdict = "pass" if r.passed else f"fail: {r.detail}"
        lines.append(f"{r.prompt:34} {r.workflow:16} {r.case:10} {r.language:4} {verdict:22} {r.latency_ms:>7}")
    passed = sum(r.passed for r in results)
    latencies = sorted(r.latency_ms for r in results)
    p50 = statistics.median(latencies) if latencies else 0
    p95 = latencies[min(len(latencies) - 1, round(0.95 * (len(latencies) - 1)))] if latencies else 0
    lines.append("-" * len(header))
    slowest = latencies[-1] if latencies else 0
    lines.append(f"passed {passed} of {len(results)}; latency p50 {p50:.0f} ms, p95 {p95} ms, max {slowest} ms")
    lines.append("(local development measurement, not an evaluation)")
    return "\n".join(lines)


def build_telemetry(settings: AppSettings) -> tuple[Telemetry, Callable[[], None]]:
    """The API's telemetry with its Langfuse exporter when ``LANGFUSE_ENABLED=true``, else none; and its flush."""
    if not settings.langfuse.enabled:
        return NoopTelemetry(), lambda: None
    observability = build_observability(
        settings.observability, langfuse=settings.langfuse, environment=settings.runtime.app_env
    )
    return observability.telemetry, observability.shutdown


async def run(settings: LLMSettings, cases: Sequence[Cassette], telemetry: Telemetry | None = None) -> list[CaseResult]:
    registry = FilePromptRegistry.from_package()
    client = build_llm_client(settings, registry=registry, clock=SystemClock(), telemetry=telemetry or NoopTelemetry())
    return [await run_case(client, cassette, index) for index, cassette in enumerate(cases, 1)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--no-env-file", action="store_true", help="read the process environment only")
    arguments = parser.parse_args(argv)
    try:
        app_settings = load_settings(env_file=None if arguments.no_env_file else Path(".env"))
        settings = app_settings.llm
        target = check_provider(settings)
        cases = load_cases()
        print(f"llm-smoke: {len(cases)} fixture cases against {target}")
        telemetry, flush = build_telemetry(app_settings)
        try:
            results = asyncio.run(run(settings, cases, telemetry))
        finally:
            flush()
    except (SmokeSetupError, ConfigurationError, SettingsError) as error:
        print(f"llm-smoke: {error}", file=sys.stderr)
        return 2
    if app_settings.langfuse.enabled:
        base = app_settings.langfuse.base_url.rstrip("/")
        print(f"llm-smoke: exported one metadata-only generation per call to {base} (Langfuse)")
    print(summarize(results))
    if results and not any(r.passed for r in results) and all(r.detail.startswith("llm_provider") for r in results):
        print("llm-smoke: every call failed at the provider; check that it is running and reachable", file=sys.stderr)
        return 2
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
