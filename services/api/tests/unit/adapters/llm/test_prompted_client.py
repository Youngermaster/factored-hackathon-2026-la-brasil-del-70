import json
from decimal import Decimal

import pytest

from bank_agent.adapters.llm.client import (
    JSON_INSTRUCTION,
    LANGUAGE_DIRECTIVES,
    PromptedLLMClient,
    describe_problems,
    parse_json_object,
)
from bank_agent.adapters.prompts.file_registry import FilePromptRegistry
from bank_agent.domain.errors import ConfigurationError, LlmInvalidOutputError, LlmTimeoutError
from bank_agent.domain.llm_outputs import DisputeSlotExtraction, EscalationSignals
from bank_agent.domain.locale import Language
from bank_agent_llm import (
    CONTEXT,
    DISPUTE_PROMPT,
    PHRASE_PROMPT,
    ScriptedCompletion,
    dispute_variables,
    phrase_variables,
)

REGISTRY = FilePromptRegistry.from_package()
VALID = json.dumps(
    {
        "intent_candidates": [{"intent": "dispute_new", "confidence": 0.9}],
        "transaction": {
            "amount": 1500,
            "currency_hint": "MXN",
            "merchant_text": "Oxxo",
            "date_expression": None,
            "channel_hint": None,
            "card_last4_hint": None,
        },
        "reason_candidates": ["unrecognized"],
    }
)


class Ticks:
    def __init__(self) -> None:
        self.value = 10.0

    def __call__(self) -> float:
        self.value += 0.125
        return self.value


def _client(completion: ScriptedCompletion) -> PromptedLLMClient:
    return PromptedLLMClient(REGISTRY, completion, monotonic=Ticks())


async def _extract(client: PromptedLLMClient, language: Language = Language.ES) -> DisputeSlotExtraction:
    result = await client.generate_structured(
        DISPUTE_PROMPT,
        dispute_variables(),
        DisputeSlotExtraction,
        language=language,
        max_output_tokens=400,
        temperature=0.0,
        call_context=CONTEXT,
    )
    assert result.prompt == DISPUTE_PROMPT
    return result.value


async def test_parses_a_valid_structured_reply_with_exact_amounts() -> None:
    completion = ScriptedCompletion([VALID])
    client = _client(completion)

    result = await client.generate_structured(
        DISPUTE_PROMPT,
        dispute_variables(),
        DisputeSlotExtraction,
        language=Language.ES,
        max_output_tokens=400,
        temperature=0.0,
        call_context=CONTEXT,
    )

    assert result.value.transaction is not None
    assert result.value.transaction.amount == Decimal(1500)
    assert not result.repaired
    assert result.usage.input_tokens == 100
    assert result.latency_ms == 125
    assert result.model_id == "test/scripted"
    assert client.model_id == "test/scripted"
    (request,) = completion.requests
    assert request.json_schema == DisputeSlotExtraction.model_json_schema()
    assert request.schema_name == "DisputeSlotExtraction"
    system, user = request.messages
    assert LANGUAGE_DIRECTIVES[Language.ES] in system.content
    assert JSON_INSTRUCTION in system.content
    assert '<data name="customer_message">' in user.content


async def test_repairs_once_with_the_validation_errors_and_sums_usage() -> None:
    broken = json.dumps({"intent_candidates": [], "reason_candidates": ["not_a_reason"]})
    completion = ScriptedCompletion([broken, VALID])

    result = await _client(completion).generate_structured(
        DISPUTE_PROMPT,
        dispute_variables(),
        DisputeSlotExtraction,
        language=Language.PT,
        max_output_tokens=400,
        temperature=0.0,
        call_context=CONTEXT,
    )

    assert result.repaired
    assert result.usage.input_tokens == 200
    second = completion.requests[1]
    assert [message.role for message in second.messages] == ["system", "user", "assistant", "user"]
    assert second.messages[2].content == broken
    repair = second.messages[3].content
    assert "transaction: Field required" in repair
    assert "reason_candidates.0" in repair
    assert "not_a_reason" not in repair
    assert LANGUAGE_DIRECTIVES[Language.PT] in second.messages[0].content


async def test_raises_invalid_output_after_one_failed_repair() -> None:
    completion = ScriptedCompletion(["not json at all", "still not json"])

    with pytest.raises(LlmInvalidOutputError, match="after one repair"):
        await _extract(_client(completion))

    assert len(completion.requests) == 2


async def test_accepts_a_fenced_json_reply() -> None:
    completion = ScriptedCompletion([f"```json\n{VALID}\n```"])

    value = await _extract(_client(completion))

    assert value.reason_candidates[0].value == "unrecognized"


async def test_provider_errors_propagate_without_a_repair() -> None:
    completion = ScriptedCompletion([LlmTimeoutError()])

    with pytest.raises(LlmTimeoutError):
        await _extract(_client(completion))

    assert len(completion.requests) == 1


async def test_text_generation_strips_and_rejects_empty_text() -> None:
    client = _client(ScriptedCompletion(["  Su saldo es 1200.00 MXN.  "]))

    result = await client.generate_text(
        PHRASE_PROMPT,
        phrase_variables(),
        language=Language.ES,
        max_output_tokens=200,
        temperature=0.2,
        call_context=CONTEXT,
    )

    assert result.text == "Su saldo es 1200.00 MXN."
    with pytest.raises(LlmInvalidOutputError, match="empty"):
        await _client(ScriptedCompletion(["   "])).generate_text(
            PHRASE_PROMPT,
            phrase_variables(),
            language=Language.ES,
            max_output_tokens=200,
            temperature=0.2,
            call_context=CONTEXT,
        )


async def test_the_text_request_carries_no_schema() -> None:
    completion = ScriptedCompletion(["Olá"])

    await _client(completion).generate_text(
        PHRASE_PROMPT,
        phrase_variables(),
        language=Language.PT,
        max_output_tokens=200,
        temperature=0.2,
        call_context=CONTEXT,
    )

    (request,) = completion.requests
    assert request.json_schema is None
    assert JSON_INSTRUCTION not in request.messages[0].content


async def test_refuses_an_output_model_the_prompt_does_not_declare() -> None:
    client = _client(ScriptedCompletion([VALID]))

    with pytest.raises(ConfigurationError, match="declares output DisputeSlotExtraction"):
        await client.generate_structured(
            DISPUTE_PROMPT,
            dispute_variables(),
            EscalationSignals,
            language=Language.ES,
            max_output_tokens=400,
            temperature=0.0,
            call_context=CONTEXT,
        )
    with pytest.raises(ConfigurationError, match="declares output DisputeSlotExtraction"):
        await client.generate_text(
            DISPUTE_PROMPT,
            dispute_variables(),
            language=Language.ES,
            max_output_tokens=400,
            temperature=0.0,
            call_context=CONTEXT,
        )


@pytest.mark.parametrize(("max_tokens", "temperature"), [(0, 0.0), (10, 2.5), (10, -0.1)])
async def test_rejects_limits_outside_the_port_preconditions(max_tokens: int, temperature: float) -> None:
    client = _client(ScriptedCompletion([VALID]))

    with pytest.raises(ValueError, match=r"max_output_tokens|temperature"):
        await client.generate_structured(
            DISPUTE_PROMPT,
            dispute_variables(),
            DisputeSlotExtraction,
            language=Language.ES,
            max_output_tokens=max_tokens,
            temperature=temperature,
            call_context=CONTEXT,
        )
    with pytest.raises(ValueError, match=r"max_output_tokens|temperature"):
        await client.generate_text(
            PHRASE_PROMPT,
            phrase_variables(),
            language=Language.ES,
            max_output_tokens=max_tokens,
            temperature=temperature,
            call_context=CONTEXT,
        )


def test_parse_json_object_rejects_arrays_and_keeps_decimals() -> None:
    assert parse_json_object('{"a": 0.1}') == {"a": Decimal("0.1")}
    with pytest.raises(ValueError, match="not a JSON object"):
        parse_json_object("[1, 2]")


def test_describe_problems_for_non_validation_errors() -> None:
    assert describe_problems(ValueError("x")) == "the reply was not a single valid JSON object"
