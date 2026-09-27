from decimal import Decimal

import pytest
from pydantic import ValidationError

from bank_agent.domain.customer import Customer
from bank_agent.domain.identifiers import TransactionId
from bank_agent.domain.intelligence import (
    DateRange,
    IntentPrediction,
    ModelRef,
    PromptRef,
    RankedCandidate,
    StructuredGeneration,
    TokenUsage,
    TransactionDescriptor,
    TransactionResolution,
)
from bank_agent.domain.workflow import Intent
from bank_agent_builders import a_date, customer

ROUTER = ModelRef.model_validate("router:keyword@1")


def test_model_and_prompt_refs_round_trip_as_strings() -> None:
    assert str(ROUTER) == "router:keyword@1"
    assert ROUTER.model_dump_json() == '"router:keyword@1"'
    prompt = PromptRef.model_validate("extract_dispute_slots@2")
    assert (prompt.prompt_id, prompt.version) == ("extract_dispute_slots", 2)
    assert str(prompt) == "extract_dispute_slots@2"


@pytest.mark.parametrize("value", ["router:keyword", "unknown:x@1", "router:Bad@1"])
def test_rejects_malformed_model_refs(value: str) -> None:
    with pytest.raises(ValidationError):
        ModelRef.model_validate(value)


@pytest.mark.parametrize("value", ["prompt", "prompt@0", "Prompt@1"])
def test_rejects_malformed_prompt_refs(value: str) -> None:
    with pytest.raises(ValidationError):
        PromptRef.model_validate(value)


def test_confidence_is_a_probability() -> None:
    with pytest.raises(ValidationError):
        IntentPrediction(intent=Intent.DISPUTE_NEW, confidence=1.5, below_threshold=False, model=ROUTER)


def test_date_interpretations_distinguish_resolved_from_ambiguous() -> None:
    march = DateRange(start=a_date(3), end=a_date(3))
    april = DateRange(start=a_date(4), end=a_date(4))
    assert TransactionDescriptor().resolved_date_range is None
    resolved = TransactionDescriptor(date_interpretations=(march,))
    assert resolved.resolved_date_range == march
    ambiguous = TransactionDescriptor(date_interpretations=(march, april))
    assert ambiguous.resolved_date_range is None
    assert ambiguous.date_is_ambiguous


def test_rejects_inverted_date_ranges() -> None:
    with pytest.raises(ValidationError):
        DateRange(start=a_date(5), end=a_date(4))


def _ranked(*ids: str) -> tuple[RankedCandidate, ...]:
    return tuple(
        RankedCandidate(transaction_id=TransactionId(tid), score=1.0 / rank, rank=rank)
        for rank, tid in enumerate(ids, 1)
    )


def test_resolution_invariants() -> None:
    ok = TransactionResolution(ranked=_ranked("T1", "T2"), margin=0.4, clear_winner=TransactionId("T1"), model=ROUTER)
    assert ok.clear_winner == "T1"
    with pytest.raises(ValidationError):
        TransactionResolution(ranked=_ranked("T1", "T1"), model=ROUTER)
    with pytest.raises(ValidationError):
        TransactionResolution(ranked=_ranked("T1", "T2"), clear_winner=TransactionId("T2"), model=ROUTER)
    with pytest.raises(ValidationError):
        TransactionResolution(
            ranked=(RankedCandidate(transaction_id=TransactionId("T1"), score=1.0, rank=2),), model=ROUTER
        )


def test_token_usage_adds_up() -> None:
    assert TokenUsage(input_tokens=3, output_tokens=1) + TokenUsage(input_tokens=2) == TokenUsage(
        input_tokens=5, output_tokens=1
    )


def test_structured_generation_is_generic_over_the_output_model() -> None:
    generation = StructuredGeneration[Customer](
        value=customer(),
        usage=TokenUsage(),
        latency_ms=5,
        model_id="fake/scripted",
        prompt=PromptRef.model_validate("extract_dispute_slots@1"),
        cost_usd=Decimal("0.001"),
    )
    assert generation.value.customer_id == customer().customer_id
