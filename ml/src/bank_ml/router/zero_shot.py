"""A hosted language model as a zero-shot intent router, and cascades behind the classical routers.

This is an offline **reference** for ``docs/evaluation/router-llm.md`` (pre-registered in
``docs/plans/router-llm.md``). Nothing here is served: the API's ``IntentRouter`` port is synchronous and production
keeps ``keyword@1``.

- **Zero-shot**: ``classify_intent_fallback@1`` with no router candidates, temperature 0, through the full gateway
  (redaction, budget, tracing, retry), so the message is redacted exactly as in production. The top label is the
  prediction and its stated confidence the confidence; the prompt's ``out_of_scope`` and ``unsupported`` both map to
  ``Intent.UNSUPPORTED``, the router's out-of-scope class.
- **Cascade**: a classical router first; the model only for messages below that router's abstention threshold.
- **Failures**: a call that still fails after the retries, or whose output fails validation after the gateway's one
  repair, is an abstention: scored as ``unsupported`` with confidence 0, below the threshold (in serving, a
  clarifying question). Failures are counted, never dropped.

Calls are recorded as cassettes (``ml/cassettes/router_llm``), so the report regenerates offline without a key. In
record mode only calls without a cassette reach the provider, with bounded concurrency, an optional request-rate
cap (the production account is shared with the live demo), and exponential backoff on rate limits.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

from bank_agent.adapters.llm.cassette import CassetteMissingError
from bank_agent.adapters.llm.prices import PER_MILLION, PriceTable
from bank_agent.bootstrap.settings import LLMSettings
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import LlmCircuitOpenError, LlmError
from bank_agent.domain.intelligence import LlmCallContext, PromptRef, PromptValue, StructuredGeneration
from bank_agent.domain.llm_outputs import FallbackIntentLabel, IntentClassification
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent
from bank_agent.ports.llm import LLMClient
from bank_ml.common.metrics import Interval, cluster_bootstrap, macro_f1
from bank_ml.common.reports import REPOSITORY_ROOT
from bank_ml.common.thresholds import ThresholdChoice, choose_threshold
from bank_ml.router.augment import Item
from bank_ml.router.evaluate import CLASSES, Scored
from bank_ml.router.models import TARGET_RISK, Predictions
from bank_ml.router.paraphrase import build_client

PROMPT: Final = PromptRef.model_validate("classify_intent_fallback@1")
MAX_OUTPUT_TOKENS: Final = 200
TEMPERATURE: Final = 0.0
CASSETTE_DIR: Final = REPOSITORY_ROOT / "ml" / "cassettes" / "router_llm"
WRITE_INTENTS: Final = (Intent.DISPUTE_NEW, Intent.CARD_BLOCK, Intent.CREDIT_APPLICATION)
"""Intents whose confident misroute starts a write or protective action flow."""
RETRY_ATTEMPTS: Final = 6
RETRY_BASE_SECONDS: Final = 2.0
RETRY_MAX_SECONDS: Final = 60.0
Sleep = Callable[[float], Awaitable[None]]
Monotonic = Callable[[], float]


@dataclass(frozen=True)
class LlmPrediction:
    """One message classified by the model, or the abstention its failure becomes."""

    item_id: str
    intent: Intent
    confidence: float
    labels: tuple[str, ...]
    latency_ms: int
    input_tokens: int
    output_tokens: int
    repaired: bool = False
    error: str | None = None

    @property
    def failed(self) -> bool:
        return self.error is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "intent": self.intent.value,
            "confidence": self.confidence,
            "labels": list(self.labels),
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "repaired": self.repaired,
            "error": self.error,
        }


def to_intent(label: FallbackIntentLabel) -> Intent:
    """The router intent of a prompt label: ``out_of_scope`` is the router's ``unsupported``."""
    return label.intent or Intent.UNSUPPORTED


def language_of(item: Item) -> Language:
    return Language.PT if item.language == "pt" else Language.ES


def variables_for(item: Item) -> dict[str, PromptValue]:
    """Zero-shot variables: the message (untrusted, redacted by the gateway), no candidates, the item's locale."""
    return {"customer_message": UntrustedText(item.text), "router_candidates": [], "dialect_hint": item.locale}


def prediction_from(item: Item, generation: StructuredGeneration[IntentClassification]) -> LlmPrediction:
    top = generation.value.candidates[0]
    return LlmPrediction(
        item_id=item.item_id,
        intent=to_intent(top.label),
        confidence=float(top.confidence),
        labels=tuple(candidate.label.value for candidate in generation.value.candidates),
        latency_ms=generation.latency_ms,
        input_tokens=generation.usage.input_tokens,
        output_tokens=generation.usage.output_tokens,
        repaired=generation.repaired,
    )


def abstention(item: Item, code: str) -> LlmPrediction:
    return LlmPrediction(item.item_id, Intent.UNSUPPORTED, 0.0, (), 0, 0, 0, error=code)


def _transient(error: LlmError) -> bool:
    return error.retryable or isinstance(error, LlmCircuitOpenError)


class RequestPacer:
    """Spaces the start of live calls to at most ``per_minute`` (no cap when ``None``)."""

    def __init__(self, per_minute: float | None, *, sleep: Sleep = asyncio.sleep, clock: Monotonic = time.monotonic):
        if per_minute is not None and per_minute <= 0:
            raise ValueError("per_minute must be positive")
        self._interval = 60.0 / per_minute if per_minute else 0.0
        self._sleep = sleep
        self._clock = clock
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        if not self._interval:
            return
        async with self._lock:
            now = self._clock()
            start = max(now, self._next)
            self._next = start + self._interval
            if start > now:
                await self._sleep(start - now)


@dataclass(frozen=True)
class ClassificationRun:
    predictions: list[LlmPrediction]
    recorded: int
    """Calls that reached ``recorder`` (the live provider) because no cassette existed."""


class ZeroShotClassifier:
    """Classifies items with ``client``; with ``recorder``, a missing cassette in ``client`` is recorded live."""

    def __init__(
        self,
        client: LLMClient,
        *,
        recorder: LLMClient | None = None,
        concurrency: int = 8,
        per_minute: float | None = None,
        sleep: Sleep = asyncio.sleep,
        clock: Monotonic = time.monotonic,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        self._client = client
        self._recorder = recorder
        self._semaphore = asyncio.Semaphore(concurrency)
        self._pacer = RequestPacer(per_minute, sleep=sleep, clock=clock)
        self._sleep = sleep
        self._recorded = 0

    async def _call(self, client: LLMClient, item: Item) -> StructuredGeneration[IntentClassification]:
        return await client.generate_structured(
            PROMPT,
            variables_for(item),
            IntentClassification,
            language=language_of(item),
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=TEMPERATURE,
            call_context=LlmCallContext(),
        )

    async def _live(self, client: LLMClient, item: Item) -> LlmPrediction:
        for attempt in range(RETRY_ATTEMPTS):
            await self._pacer.wait()
            try:
                return prediction_from(item, await self._call(client, item))
            except LlmError as error:
                if not _transient(error) or attempt + 1 == RETRY_ATTEMPTS:
                    return abstention(item, error.code)
                await self._sleep(min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * 2.0**attempt))
        raise AssertionError("unreachable: the last attempt always returns")  # pragma: no cover

    async def _one(self, item: Item) -> LlmPrediction:
        async with self._semaphore:
            if self._recorder is None:
                return await self._live(self._client, item)
            try:
                return prediction_from(item, await self._call(self._client, item))
            except CassetteMissingError:
                self._recorded += 1
                return await self._live(self._recorder, item)
            except LlmError as error:
                return abstention(item, error.code)

    async def classify(self, items: Sequence[Item]) -> ClassificationRun:
        predictions = await asyncio.gather(*(self._one(item) for item in items))
        return ClassificationRun(list(predictions), self._recorded)


# --- systems -------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SystemRun:
    """One routing system on one split: predictions plus the per-message model usage it implies."""

    name: str
    predictions: Predictions
    called: NDArray[np.bool_]
    latency_ms: NDArray[np.float64]
    input_tokens: NDArray[np.int64]
    output_tokens: NDArray[np.int64]
    failed: NDArray[np.bool_]
    repaired: NDArray[np.bool_]
    model_id: str | None = None


def classical_run(name: str, predictions: Predictions, latency_ms: NDArray[np.float64]) -> SystemRun:
    size = len(predictions.intents)
    no = np.zeros(size, dtype=bool)
    zeros = np.zeros(size, dtype=np.int64)
    return SystemRun(name, predictions, no, latency_ms, zeros, zeros.copy(), no.copy(), no.copy())


def _llm_arrays(llm: Sequence[LlmPrediction]) -> dict[str, NDArray[Any]]:
    return {
        "confidence": np.array([p.confidence for p in llm], dtype=np.float64),
        "latency": np.array([p.latency_ms for p in llm], dtype=np.float64),
        "input": np.array([p.input_tokens for p in llm], dtype=np.int64),
        "output": np.array([p.output_tokens for p in llm], dtype=np.int64),
        "failed": np.array([p.failed for p in llm], dtype=bool),
        "repaired": np.array([p.repaired for p in llm], dtype=bool),
    }


def correct_mask(items: Sequence[Item], intents: Sequence[Intent]) -> NDArray[np.bool_]:
    return np.array([item.intent is intent for item, intent in zip(items, intents, strict=True)], dtype=bool)


def choose_llm_threshold(
    items: Sequence[Item], llm: Sequence[LlmPrediction], mask: NDArray[np.bool_] | None = None
) -> ThresholdChoice:
    """The dev threshold on the model's stated confidence (at most ``TARGET_RISK`` error among covered items),
    over the items in ``mask`` (all by default). Failures have confidence 0, so they are never covered."""
    arrays = _llm_arrays(llm)
    correct = correct_mask(items, [p.intent for p in llm]) & ~arrays["failed"]
    chosen = np.ones(len(items), dtype=bool) if mask is None else mask
    return choose_threshold(arrays["confidence"][chosen], correct[chosen], TARGET_RISK)


def zero_shot_run(name: str, model_id: str, llm: Sequence[LlmPrediction], threshold: float) -> SystemRun:
    arrays = _llm_arrays(llm)
    below = (arrays["confidence"] < threshold) | arrays["failed"]
    predictions = Predictions([p.intent for p in llm], arrays["confidence"], below)
    called = np.ones(len(llm), dtype=bool)
    return SystemRun(
        name,
        predictions,
        called,
        arrays["latency"],
        arrays["input"],
        arrays["output"],
        arrays["failed"],
        arrays["repaired"],
        model_id,
    )


def cascade_run(name: str, base: SystemRun, model_id: str, llm: Sequence[LlmPrediction], threshold: float) -> SystemRun:
    """``base`` where it is at or above its own threshold, the model below it (with the model's threshold)."""
    arrays = _llm_arrays(llm)
    handed = base.predictions.below_threshold.copy()
    intents = [p.intent if h else b for p, b, h in zip(llm, base.predictions.intents, handed, strict=True)]
    confidence = np.where(handed, arrays["confidence"], base.predictions.confidence)
    llm_below = (arrays["confidence"] < threshold) | arrays["failed"]
    below = np.where(handed, llm_below, False)
    zero = np.zeros(len(llm), dtype=np.int64)
    return SystemRun(
        name,
        Predictions(intents, confidence, below),
        handed,
        base.latency_ms + np.where(handed, arrays["latency"], 0.0),
        np.where(handed, arrays["input"], zero),
        np.where(handed, arrays["output"], zero),
        handed & arrays["failed"],
        handed & arrays["repaired"],
        model_id,
    )


# --- metrics beyond the shared router evaluation -------------------------------------------------------------


def write_misroutes(items: Sequence[Item], run: SystemRun) -> int:
    """Covered, wrong, and predicted as a write intent: a confident start of the wrong write flow."""
    covered = ~run.predictions.below_threshold
    return sum(
        1
        for item, intent, ok in zip(items, run.predictions.intents, covered, strict=True)
        if ok and intent in WRITE_INTENTS and intent is not item.intent
    )


def out_of_scope_confident_misroutes(items: Sequence[Item], run: SystemRun) -> int:
    """Out-of-scope items the system confidently sent into a workflow."""
    covered = ~run.predictions.below_threshold
    return sum(
        1
        for item, intent, ok in zip(items, run.predictions.intents, covered, strict=True)
        if ok and item.intent is Intent.UNSUPPORTED and intent is not Intent.UNSUPPORTED
    )


def percentile(values: NDArray[np.float64], q: float) -> float:
    return float(np.percentile(values, q)) if len(values) else 0.0


def usage(run: SystemRun, prices: PriceTable) -> dict[str, Any]:
    """Model share, latency per message, tokens per call, and list-price cost per 1,000 messages."""
    size = len(run.called)
    calls = int(run.called.sum())
    result: dict[str, Any] = {
        "messages": size,
        "model_calls": calls,
        "model_share": calls / size if size else 0.0,
        "latency_ms_p50": percentile(run.latency_ms, 50),
        "latency_ms_p95": percentile(run.latency_ms, 95),
        "model_call_ms_p50": percentile(run.latency_ms[run.called], 50) if calls else None,
        "model_call_ms_p95": percentile(run.latency_ms[run.called], 95) if calls else None,
        "failures": int(run.failed.sum()),
        "repaired": int(run.repaired.sum()),
        "input_tokens_per_call": float(run.input_tokens[run.called].mean()) if calls else 0.0,
        "output_tokens_per_call": float(run.output_tokens[run.called].mean()) if calls else 0.0,
        "cost_usd_per_1000": "0",
        "price_basis": None,
    }
    if run.model_id is not None and size:
        entry = {price.model_id: price for price in prices.entries}.get(run.model_id)
        if entry is not None:
            total = (
                Decimal(int(run.input_tokens.sum())) * entry.input_usd_per_million
                + Decimal(int(run.output_tokens.sum())) * entry.output_usd_per_million
            ) / PER_MILLION
            per_thousand = total * Decimal(1000) / Decimal(size)
            result["cost_usd_per_1000"] = str(per_thousand.quantize(Decimal("0.0001")))
            result["price_basis"] = {
                "model_id": entry.model_id,
                "input_usd_per_million": str(entry.input_usd_per_million),
                "output_usd_per_million": str(entry.output_usd_per_million),
                "effective_date": entry.effective_date.isoformat(),
                "verified": entry.verified,
            }
        else:
            result["cost_usd_per_1000"] = None
    return result


def paired_macro_f1_difference(first: Scored, second: Scored) -> Interval:
    """Macro-F1 of ``first`` minus ``second`` on the same items, resampling seed groups jointly."""
    if [item.item_id for item in first.items] != [item.item_id for item in second.items]:
        raise ValueError("a paired difference needs the same items in the same order")
    size = len(CLASSES)

    def difference(idx: NDArray[np.int64]) -> float:
        return macro_f1(first.truth[idx], first.predicted[idx], size) - macro_f1(
            second.truth[idx], second.predicted[idx], size
        )

    return cluster_bootstrap(first.groups, difference, name=f"paired:{first.name}:{second.name}")


def timed_route(router: Any, items: Sequence[Item]) -> tuple[Predictions, NDArray[np.float64]]:
    """Route every item through an ``IntentRouter`` and time each call in process (one warm-up pass first)."""
    for item in items[: min(len(items), 50)]:
        router.route(UntrustedText(item.text), language_of(item))
    intents: list[Intent] = []
    confidence: list[float] = []
    below: list[bool] = []
    latency: list[float] = []
    for item in items:
        start = time.perf_counter_ns()
        prediction = router.route(UntrustedText(item.text), language_of(item))
        latency.append((time.perf_counter_ns() - start) / 1e6)
        intents.append(prediction.intent)
        confidence.append(prediction.confidence)
        below.append(prediction.below_threshold)
    return (
        Predictions(intents, np.array(confidence, dtype=np.float64), np.array(below, dtype=bool)),
        np.array(latency, dtype=np.float64),
    )


# --- clients -------------------------------------------------------------------------------------------------

REPLAY_BUDGET_USD: Final = Decimal(1000)
"""Replays spend nothing; the replay gateway's daily cap only has to stay out of the way of the priced replies."""


def cassette_client(model_id: str, cassette_dir: Path, *, record: bool, budget_usd: Decimal) -> LLMClient:
    """The full gateway over cassettes for ``model_id``: replay only, or record through the live provider
    (``LLM_API_BASE`` and ``LLM_API_KEY_PRIMARY`` from the environment). A fallback model is never configured, so
    every recorded reply comes from ``model_id``."""
    settings = LLMSettings(
        provider="cassette",
        cassette_mode="record" if record else "replay",
        primary_model=model_id,
        fallback_model="",
        cassette_dir=cassette_dir,
        daily_budget_usd=budget_usd if record else REPLAY_BUDGET_USD,
    )
    return build_client(settings)


async def classify_items(
    model_id: str,
    items: Sequence[Item],
    cassette_dir: Path,
    *,
    record: bool = False,
    concurrency: int = 8,
    per_minute: float | None = None,
    budget_usd: Decimal = Decimal(10),
) -> ClassificationRun:
    """Replay every item's cassette; with ``record``, call the provider for the items that have none."""
    replay = cassette_client(model_id, cassette_dir, record=False, budget_usd=budget_usd)
    recorder = cassette_client(model_id, cassette_dir, record=True, budget_usd=budget_usd) if record else None
    classifier = ZeroShotClassifier(replay, recorder=recorder, concurrency=concurrency, per_minute=per_minute)
    return await classifier.classify(items)
