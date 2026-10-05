"""The hosted language model router reference: calls through a scripted ``FakeLLM`` (never a live model), the label
mapping, failures as abstentions, retry and pacing, cascades, thresholds on dev, cost arithmetic, and the decision."""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from pydantic import BaseModel

from bank_agent.adapters.llm.cassette import CassetteLLM, CassetteMissingError, CassetteMode
from bank_agent.adapters.llm.prices import ModelPrice, PriceTable, PriceTableFile
from bank_agent.adapters.llm.redaction import Redactor
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.domain.errors import LlmInvalidOutputError, LlmRateLimitedError
from bank_agent.domain.intelligence import (
    LlmCallContext,
    PromptRef,
    PromptValue,
    StructuredGeneration,
    TextGeneration,
    TokenUsage,
)
from bank_agent.domain.llm_outputs import FallbackIntentLabel
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent
from bank_agent.testing.fake_llm import FakeLLM, ScriptedError, ScriptedResponse
from bank_ml.router.augment import Item
from bank_ml.router.evaluate import Scored
from bank_ml.router.models import Predictions
from bank_ml.router.zero_shot import (
    PROMPT,
    RETRY_ATTEMPTS,
    RETRY_MAX_SECONDS,
    LlmPrediction,
    RequestPacer,
    ZeroShotClassifier,
    cascade_run,
    choose_llm_threshold,
    classical_run,
    classify_items,
    out_of_scope_confident_misroutes,
    paired_macro_f1_difference,
    to_intent,
    usage,
    write_misroutes,
    zero_shot_run,
)
from bank_ml.router.zero_shot_report import (
    DECISION_BEGIN,
    DECISION_END,
    PENDING_DECISION,
    DecisionRule,
    cascade_name,
    decide,
    existing_decision,
)


def _item(number: int, intent: Intent, locale: str = "es-MX", group: str | None = None) -> Item:
    return Item(
        item_id=f"i{number:03d}",
        seed_id=f"s{number:03d}",
        intent=intent,
        locale=locale,
        text=f"mensaje {number}",
        provenance="team_authored",
        augmentation="canonical",
        group_id=group or f"g{number:03d}",
        split="dev",
    )


def _reply(label: str, confidence: float = 0.9, *, tokens: tuple[int, int] = (900, 30)) -> ScriptedResponse:
    return ScriptedResponse(
        {"candidates": [{"label": label, "confidence": confidence}]},
        usage=TokenUsage(input_tokens=tokens[0], output_tokens=tokens[1]),
        latency_ms=700,
    )


def _prediction(item: Item, intent: Intent, confidence: float, *, error: str | None = None) -> LlmPrediction:
    return LlmPrediction(item.item_id, intent, confidence, (intent.value,), 800, 900, 30, error=error)


class Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class MissingCassettes:
    """Replay that has no cassette for anything."""

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
        raise CassetteMissingError("no cassette")

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
        raise CassetteMissingError("no cassette")


def test_every_prompt_label_maps_to_a_router_intent() -> None:
    assert to_intent(FallbackIntentLabel.OUT_OF_SCOPE) is Intent.UNSUPPORTED
    assert to_intent(FallbackIntentLabel.UNSUPPORTED) is Intent.UNSUPPORTED
    for label in FallbackIntentLabel:
        if label is not FallbackIntentLabel.OUT_OF_SCOPE:
            assert to_intent(label) is Intent(label.value)


async def test_classifies_zero_shot_with_the_items_locale_and_language() -> None:
    fake = FakeLLM()
    fake.script(PROMPT, _reply("card_block", 0.95))
    items = [_item(1, Intent.CARD_BLOCK), _item(2, Intent.CARD_BLOCK, locale="pt-BR")]
    run = await ZeroShotClassifier(fake).classify(items)
    first = run.predictions[0]
    assert (first.intent, first.confidence, first.labels) == (Intent.CARD_BLOCK, 0.95, ("card_block",))
    assert (first.input_tokens, first.output_tokens, first.latency_ms, first.failed) == (900, 30, 700, False)
    assert fake.calls[0].variables["router_candidates"] == []
    assert fake.calls[0].variables["dialect_hint"] == "es-MX"
    assert [call.language for call in fake.calls] == [Language.ES, Language.PT]
    assert run.recorded == 0


async def test_out_of_scope_label_becomes_unsupported() -> None:
    fake = FakeLLM()
    fake.script(PROMPT, _reply("out_of_scope", 0.8))
    run = await ZeroShotClassifier(fake).classify([_item(1, Intent.UNSUPPORTED)])
    assert run.predictions[0].intent is Intent.UNSUPPORTED


async def test_invalid_output_is_an_abstention_and_not_retried() -> None:
    fake = FakeLLM()
    fake.script(PROMPT, ScriptedError(LlmInvalidOutputError))
    sleeps = Sleeps()
    run = await ZeroShotClassifier(fake, sleep=sleeps).classify([_item(1, Intent.CARD_BLOCK)])
    prediction = run.predictions[0]
    assert (prediction.intent, prediction.confidence, prediction.error) == (
        Intent.UNSUPPORTED,
        0.0,
        "llm_invalid_output",
    )
    assert prediction.failed
    assert len(fake.calls) == 1
    assert sleeps.delays == []


async def test_rate_limits_are_retried_with_backoff() -> None:
    fake = FakeLLM()
    fake.script(PROMPT, ScriptedError(LlmRateLimitedError), ScriptedError(LlmRateLimitedError), _reply("card_status"))
    sleeps = Sleeps()
    run = await ZeroShotClassifier(fake, sleep=sleeps).classify([_item(1, Intent.CARD_STATUS)])
    assert run.predictions[0].intent is Intent.CARD_STATUS
    assert sleeps.delays == [2.0, 4.0]


async def test_a_persistent_rate_limit_ends_as_an_abstention_after_capped_backoff() -> None:
    fake = FakeLLM()
    fake.script(PROMPT, ScriptedError(LlmRateLimitedError))
    sleeps = Sleeps()
    run = await ZeroShotClassifier(fake, sleep=sleeps).classify([_item(1, Intent.CARD_STATUS)])
    assert run.predictions[0].error == "llm_rate_limited"
    assert len(fake.calls) == RETRY_ATTEMPTS
    assert len(sleeps.delays) == RETRY_ATTEMPTS - 1
    assert max(sleeps.delays) <= RETRY_MAX_SECONDS


async def test_record_mode_calls_the_provider_only_for_missing_cassettes() -> None:
    recorder = FakeLLM()
    recorder.script(PROMPT, _reply("balance_inquiry"))
    run = await ZeroShotClassifier(MissingCassettes(), recorder=recorder).classify([_item(1, Intent.BALANCE_INQUIRY)])
    assert run.recorded == 1
    assert run.predictions[0].intent is Intent.BALANCE_INQUIRY
    replay = FakeLLM()
    replay.script(PROMPT, _reply("balance_inquiry"))
    untouched = FakeLLM()
    again = await ZeroShotClassifier(replay, recorder=untouched).classify([_item(1, Intent.BALANCE_INQUIRY)])
    assert again.recorded == 0
    assert untouched.calls == []


async def test_replay_without_a_cassette_fails_loudly() -> None:
    with pytest.raises(CassetteMissingError):
        await ZeroShotClassifier(MissingCassettes()).classify([_item(1, Intent.BALANCE_INQUIRY)])


async def test_the_pacer_spaces_live_calls() -> None:
    sleeps = Sleeps()
    now = [100.0]
    pacer = RequestPacer(30, sleep=sleeps, clock=lambda: now[0])
    for _ in range(3):
        await pacer.wait()
    assert sleeps.delays == [2.0, 4.0]
    unlimited = RequestPacer(None, sleep=sleeps)
    await unlimited.wait()
    assert len(sleeps.delays) == 2
    with pytest.raises(ValueError, match="positive"):
        RequestPacer(0)
    with pytest.raises(ValueError, match="concurrency"):
        ZeroShotClassifier(FakeLLM(), concurrency=0)


ITEMS = [
    _item(1, Intent.CARD_BLOCK, group="a"),
    _item(2, Intent.DISPUTE_NEW, group="a"),
    _item(3, Intent.UNSUPPORTED, group="b"),
    _item(4, Intent.BALANCE_INQUIRY, group="c"),
]


def _base() -> Predictions:
    return Predictions(
        [Intent.CARD_BLOCK, Intent.CARD_BLOCK, Intent.CREDIT_PRODUCT_INFO, Intent.BALANCE_INQUIRY],
        np.array([0.95, 0.5, 0.4, 0.99]),
        np.array([False, True, True, False]),
    )


def _llm() -> list[LlmPrediction]:
    return [
        _prediction(ITEMS[0], Intent.CARD_STATUS, 0.9),
        _prediction(ITEMS[1], Intent.DISPUTE_NEW, 0.95),
        _prediction(ITEMS[2], Intent.UNSUPPORTED, 0.0, error="llm_invalid_output"),
        _prediction(ITEMS[3], Intent.BALANCE_INQUIRY, 0.6),
    ]


def test_zero_shot_abstains_below_its_threshold_and_on_failures() -> None:
    run = zero_shot_run("zs", "azure/m", _llm(), threshold=0.9)
    assert run.predictions.below_threshold.tolist() == [False, False, True, True]
    assert run.called.all()
    assert run.failed.tolist() == [False, False, True, False]


def test_the_cascade_keeps_confident_base_predictions_and_hands_the_rest_to_the_model() -> None:
    base = classical_run("tfidf", _base(), np.full(4, 0.5))
    run = cascade_run("cascade", base, "azure/m", _llm(), threshold=0.9)
    assert run.predictions.intents == [
        Intent.CARD_BLOCK,
        Intent.DISPUTE_NEW,
        Intent.UNSUPPORTED,
        Intent.BALANCE_INQUIRY,
    ]
    assert run.called.tolist() == [False, True, True, False]
    assert run.predictions.below_threshold.tolist() == [False, False, True, False]
    assert run.input_tokens.tolist() == [0, 900, 900, 0]
    assert run.latency_ms.tolist() == [0.5, 800.5, 800.5, 0.5]
    assert run.failed.tolist() == [False, False, True, False]


def test_the_model_threshold_is_chosen_on_the_given_items_only() -> None:
    choice = choose_llm_threshold(ITEMS, _llm())
    assert choice.met
    assert choice.risk <= 0.05
    handed = np.array([False, True, True, False])
    restricted = choose_llm_threshold(ITEMS, _llm(), handed)
    assert restricted.coverage == pytest.approx(0.5)


def test_confident_misroutes_count_write_intents_and_out_of_scope() -> None:
    base = classical_run("tfidf", _base(), np.zeros(4))
    assert write_misroutes(ITEMS, base) == 0
    confident = classical_run(
        "x",
        Predictions(
            [Intent.CARD_BLOCK, Intent.CARD_BLOCK, Intent.DISPUTE_NEW, Intent.BALANCE_INQUIRY],
            np.ones(4),
            np.zeros(4, dtype=bool),
        ),
        np.zeros(4),
    )
    assert write_misroutes(ITEMS, confident) == 2
    assert out_of_scope_confident_misroutes(ITEMS, confident) == 1


def _prices(verified: bool = True) -> PriceTable:
    entry = ModelPrice(
        model_id="azure/m",
        input_usd_per_million=Decimal("0.40"),
        output_usd_per_million=Decimal("1.60"),
        effective_date=date(2025, 4, 1),
        source_url="https://prices.azure.com/api/retail/prices",
        verified=verified,
    )
    return PriceTable(
        PriceTableFile(schema_version=1, currency="USD", unverified_price_multiplier=Decimal(2), models=(entry,))
    )


def test_cost_per_thousand_messages_uses_measured_tokens_at_list_price() -> None:
    llm = [_prediction(item, item.intent, 0.9) for item in ITEMS]
    zero_shot = usage(zero_shot_run("zs", "azure/m", llm, 0.5), _prices(verified=False))
    # (900 * 0.40 + 30 * 1.60) / 1e6 per message = 0.000408 USD, so 0.408 per 1,000 (list price, no multiplier)
    assert zero_shot["cost_usd_per_1000"] == "0.4080"
    assert zero_shot["model_share"] == 1.0
    assert zero_shot["price_basis"]["verified"] is False
    base = classical_run("tfidf", _base(), np.zeros(4))
    cascade = usage(cascade_run("c", base, "azure/m", llm, 0.5), _prices())
    assert cascade["cost_usd_per_1000"] == "0.2040"
    assert cascade["model_share"] == 0.5
    assert usage(base, _prices())["cost_usd_per_1000"] == "0"
    assert usage(zero_shot_run("zs", "azure/unknown", llm, 0.5), _prices())["cost_usd_per_1000"] is None


def test_a_paired_difference_needs_the_same_items() -> None:
    first = Scored("a", ITEMS, _base())
    same = paired_macro_f1_difference(first, Scored("b", ITEMS, _base()))
    assert (same.estimate, same.low, same.high) == (0.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="same items"):
        paired_macro_f1_difference(first, Scored("c", ITEMS[:3], _subset_base()))


def _subset_base() -> Predictions:
    base = _base()
    return Predictions(base.intents[:3], base.confidence[:3], base.below_threshold[:3])


def _dev_row(recall: float, writes: int, share: float, p95: float | None, cost: str | None) -> dict[str, object]:
    return {
        "high_stakes_recall_mean": recall,
        "write_misroutes": writes,
        "usage": {"model_share": share, "model_call_ms_p95": p95, "cost_usd_per_1000": cost},
    }


def _scored(name: str, intents: Sequence[Intent]) -> Scored:
    return Scored(name, ITEMS, Predictions(list(intents), np.ones(4), np.zeros(4, dtype=bool)))


def test_the_rule_recommends_only_a_cascade_meeting_every_criterion() -> None:
    truth = [item.intent for item in ITEMS]
    wrong = [Intent.CARD_STATUS, Intent.CARD_STATUS, Intent.CARD_STATUS, Intent.CARD_STATUS]
    scored = {
        "tfidf": _scored("tfidf", wrong),
        cascade_name("tfidf", "cheap"): _scored("cheap", truth),
        cascade_name("tfidf", "dear"): _scored("dear", truth),
    }
    dev = {
        "tfidf": _dev_row(0.5, 0, 0.0, None, "0"),
        cascade_name("tfidf", "cheap"): _dev_row(0.6, 1, 0.5, 900.0, "0.20"),
        cascade_name("tfidf", "dear"): _dev_row(0.6, 1, 0.5, 900.0, "1.50"),
    }
    result = decide(dev, scored, ["dear", "cheap"], "tfidf", DecisionRule())
    assert result["qualifying"] == ["cheap"]
    assert result["chosen"] == "cheap"
    dearest_criteria = result["candidates"]["dear"]["criteria"]
    assert [row["met"] for row in dearest_criteria] == [True, True, True, True, True, False]
    lenient = decide(dev, scored, ["dear", "cheap"], "tfidf", DecisionRule(max_cost_usd_per_1000=Decimal(5)))
    assert lenient["qualifying"] == ["dear", "cheap"]
    assert lenient["model_comparison"]["difference"]["estimate"] == 0.0
    assert lenient["chosen"] == "cheap"  # the interval contains 0, so the cheaper model wins
    dev[cascade_name("tfidf", "cheap")] = _dev_row(0.3, 5, 0.9, 3000.0, None)
    none = decide(dev, scored, ["cheap"], "tfidf", DecisionRule())
    assert none["chosen"] is None
    assert not any(row["met"] for row in none["candidates"]["cheap"]["criteria"][1:])


def test_the_hand_written_decision_survives_regeneration(tmp_path: Path) -> None:
    report = tmp_path / "router-llm.md"
    assert existing_decision(report) == PENDING_DECISION
    report.write_text(f"# Report\n\n{DECISION_BEGIN}\n\nKeep keyword@1.\n\n{DECISION_END}\n", encoding="utf-8")
    assert existing_decision(report) == "Keep keyword@1."
    report.write_text("# Report without markers\n", encoding="utf-8")
    assert existing_decision(report) == PENDING_DECISION


async def test_replays_a_recorded_cassette_through_the_full_gateway_without_a_key(tmp_path: Path) -> None:
    item = _item(1, Intent.CARD_BLOCK)
    fake = FakeLLM()
    fake.script(PROMPT, _reply("card_block", 0.95))
    recorder = CassetteLLM(
        tmp_path, model_id="azure/m", redactor=Redactor(), clock=SystemClock(), mode=CassetteMode.RECORD, inner=fake
    )
    await ZeroShotClassifier(recorder).classify([item])
    replayed = await classify_items("azure/m", [item], tmp_path)
    assert replayed.predictions[0].intent is Intent.CARD_BLOCK
    assert replayed.predictions[0].input_tokens == 900
    assert replayed.recorded == 0
    with pytest.raises(CassetteMissingError):
        await classify_items("azure/other", [item], tmp_path)
