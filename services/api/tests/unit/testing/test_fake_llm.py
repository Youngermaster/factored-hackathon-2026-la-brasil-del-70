from decimal import Decimal

import pytest
from pydantic import BaseModel

from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import LlmInvalidOutputError, LlmTimeoutError
from bank_agent.domain.intelligence import LlmCallContext, PromptRef, PromptValue, TokenUsage
from bank_agent.domain.locale import Language
from bank_agent.domain.money import Currency, Money
from bank_agent.testing.fake_llm import (
    FakeLLM,
    FakeLLMScriptMissingError,
    ScriptedError,
    ScriptedResponse,
    canonical_variables,
    input_hash,
    scripted_calls,
)

SLOTS = PromptRef.model_validate("extract_dispute_slots@1")
PHRASE = PromptRef.model_validate("phrase_response@1")
CONTEXT = LlmCallContext()


class Slots(BaseModel):
    merchant: str | None


async def _structured(fake: FakeLLM, variables: dict[str, PromptValue]) -> Slots:
    result = await fake.generate_structured(
        SLOTS,
        variables,
        Slots,
        language=Language.ES,
        max_output_tokens=200,
        temperature=0.0,
        call_context=CONTEXT,
    )
    return result.value


def test_input_hash_ignores_key_order_and_normalizes_values() -> None:
    first: dict[str, PromptValue] = {
        "b": Decimal("1.50"),
        "a": UntrustedText("hola"),
        "m": Money.of("2", Currency.MXN),
        "l": ["x"],
    }
    second = dict(reversed(list(first.items())))
    assert canonical_variables(first) == canonical_variables(second)
    assert input_hash(SLOTS, first) == input_hash(SLOTS, second)
    assert input_hash(SLOTS, first) != input_hash(PHRASE, first)


async def test_serves_exact_scripts_before_the_wildcard() -> None:
    fake = FakeLLM()
    fake.script(SLOTS, ScriptedResponse(output={"merchant": "exact"}), variables={"text": "a"})
    fake.script(SLOTS, ScriptedResponse(output={"merchant": "any"}))
    assert (await _structured(fake, {"text": "a"})).merchant == "exact"
    assert (await _structured(fake, {"text": "b"})).merchant == "any"
    assert len(scripted_calls(fake, SLOTS)) == 2


async def test_queues_responses_and_repeats_the_last_one() -> None:
    fake = FakeLLM()
    fake.script(SLOTS, ScriptedError(LlmTimeoutError), ScriptedResponse(output={"merchant": "ok"}))
    with pytest.raises(LlmTimeoutError):
        await _structured(fake, {})
    assert (await _structured(fake, {})).merchant == "ok"
    assert (await _structured(fake, {})).merchant == "ok"


async def test_an_unscripted_call_fails_loudly() -> None:
    with pytest.raises(FakeLLMScriptMissingError):
        await _structured(FakeLLM(), {})


def test_refuses_an_empty_script() -> None:
    with pytest.raises(ValueError, match="at least one"):
        FakeLLM().script(SLOTS)


async def test_invalid_structured_output_raises_the_typed_error() -> None:
    fake = FakeLLM()
    fake.script(SLOTS, ScriptedResponse(output={"merchant": 3}), ScriptedResponse(output="text"))
    with pytest.raises(LlmInvalidOutputError):
        await _structured(fake, {})
    with pytest.raises(LlmInvalidOutputError):
        await _structured(fake, {})


async def test_text_generation_carries_usage_and_cost() -> None:
    fake = FakeLLM()
    usage = TokenUsage(input_tokens=10, output_tokens=5)
    fake.script(PHRASE, ScriptedResponse(output="Hola", usage=usage, cost_usd=Decimal("0.001"), latency_ms=7))
    result = await fake.generate_text(
        PHRASE, {}, language=Language.PT, max_output_tokens=50, temperature=0.2, call_context=CONTEXT
    )
    assert (result.text, result.usage, result.cost_usd, result.latency_ms) == ("Hola", usage, Decimal("0.001"), 7)
    assert fake.calls[0].language is Language.PT
    assert not fake.calls[0].structured


async def test_text_generation_rejects_a_mapping_output() -> None:
    fake = FakeLLM()
    fake.script(PHRASE, ScriptedResponse(output={"not": "text"}))
    with pytest.raises(LlmInvalidOutputError):
        await fake.generate_text(
            PHRASE, {}, language=Language.ES, max_output_tokens=50, temperature=0.0, call_context=CONTEXT
        )


@pytest.mark.parametrize(("tokens", "temperature"), [(0, 0.0), (10, -0.1), (10, 2.5)])
async def test_rejects_out_of_range_generation_limits(tokens: int, temperature: float) -> None:
    fake = FakeLLM()
    fake.script(PHRASE, ScriptedResponse(output="x"))
    with pytest.raises(ValueError, match="must"):
        await fake.generate_text(
            PHRASE, {}, language=Language.ES, max_output_tokens=tokens, temperature=temperature, call_context=CONTEXT
        )
