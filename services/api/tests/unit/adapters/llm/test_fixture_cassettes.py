"""The committed cassettes: one per extraction prompt, language, and case, each replayable and well-formed.

Until a provider is chosen these are hand-authored fixtures (``provenance: hand_authored_fixture``); the tests
check parsing and replay, not model quality.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from bank_agent.adapters.llm.cassette import (
    FIXTURE_MODEL_ID,
    Cassette,
    CassetteLLM,
    Provenance,
    load_cassette,
)
from bank_agent.adapters.llm.redaction import Redactor
from bank_agent.adapters.prompts.file_registry import FilePromptRegistry
from bank_agent.bootstrap.settings import DEFAULT_CASSETTE_DIR
from bank_agent.domain.intelligence import LlmCallContext, PromptValue
from bank_agent.domain.llm_outputs import (
    OUTPUT_MODELS,
    AccountInquirySlotExtraction,
    CardSupportSlotExtraction,
    CreditSlotExtraction,
    DisputeSlotExtraction,
)
from bank_agent.domain.workflow import Intent
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_agent.testing.clock import FixedClock

EXTRACTION_PROMPTS = {
    "extract_dispute_slots@1": "dispute",
    "extract_account_inquiry_slots@1": "account_inquiry",
    "extract_card_support_slots@1": "card_support",
    "extract_credit_slots@1": "credit",
}
CASES = ("normal", "ambiguous", "out_of_scope")
LANGUAGES = ("es", "pt")


def _load_all() -> list[tuple[Path, Cassette]]:
    return [(path, load_cassette(path)) for path in sorted(DEFAULT_CASSETTE_DIR.rglob("*.json"))]


ALL = _load_all()
EXTRACTIONS = [cassette for _, cassette in ALL if str(cassette.prompt) in EXTRACTION_PROMPTS]


def test_cassettes_exist_and_every_file_is_keyed_by_its_content() -> None:
    assert len(ALL) >= 32
    for path, cassette in ALL:
        assert path.stem == cassette.cassette_id
        assert path.parent.name == str(cassette.prompt.version)
        assert path.parent.parent.name == cassette.prompt.prompt_id


def test_fixtures_are_labeled_and_never_pass_as_recordings() -> None:
    for _, cassette in ALL:
        if cassette.provenance is Provenance.HAND_AUTHORED_FIXTURE:
            assert cassette.model_id == FIXTURE_MODEL_ID
            assert "Hand-authored fixture" in cassette.note
        else:
            assert cassette.model_id != FIXTURE_MODEL_ID


def test_every_cassette_matches_a_shipped_prompt_and_its_declared_variables() -> None:
    registry = FilePromptRegistry.from_package()
    for _, cassette in ALL:
        template = registry.get(cassette.prompt)
        assert template.output_model == cassette.output_model
        assert set(cassette.variables) <= set(template.variables)


def test_each_extraction_prompt_has_es_and_pt_normal_ambiguous_and_out_of_scope_cases() -> None:
    present = {(str(c.prompt), c.language.value, c.labels["case"]) for c in EXTRACTIONS}

    assert present == {
        (prompt, language, case) for prompt in EXTRACTION_PROMPTS for language in LANGUAGES for case in CASES
    }
    for cassette in EXTRACTIONS:
        assert cassette.labels["workflow"] == EXTRACTION_PROMPTS[str(cassette.prompt)]


def _variables(cassette: Cassette) -> dict[str, PromptValue]:
    return {key: value for key, value in cassette.variables.items() if isinstance(value, str | list)}  # type: ignore[misc]


async def _replay(cassette: Cassette) -> BaseModel:
    client = CassetteLLM(
        DEFAULT_CASSETTE_DIR,
        model_id=cassette.model_id,
        redactor=Redactor(),
        clock=FixedClock(datetime(2026, 9, 26, tzinfo=UTC)),
    )
    assert cassette.output_model is not None
    result = await client.generate_structured(
        cassette.prompt,
        _variables(cassette),
        OUTPUT_MODELS[cassette.output_model],
        language=cassette.language,
        max_output_tokens=400,
        temperature=0.0,
        call_context=LlmCallContext(),
    )
    return result.value


def _dispute(value: Any, case: str) -> None:
    assert isinstance(value, DisputeSlotExtraction)
    dispute_intents = {Intent.DISPUTE_NEW, Intent.DISPUTE_STATUS}
    if case == "normal":
        assert value.transaction is not None
        assert value.transaction.amount is not None
        assert value.reason_candidates
        assert value.intent_candidates[0].intent in dispute_intents
    elif case == "ambiguous":
        assert value.transaction is None or value.transaction.amount is None
        assert len(value.intent_candidates) > 1
    else:
        assert value.transaction is None
        assert value.reason_candidates == ()
        assert not {candidate.intent for candidate in value.intent_candidates} & dispute_intents


def _account(value: Any, case: str) -> None:
    assert isinstance(value, AccountInquirySlotExtraction)
    if case == "normal":
        assert value.product_hint is not None
    elif case == "ambiguous":
        assert value.product_hint is None
        assert value.payment is not None
    else:
        assert (value.product_hint, value.statement_period_expression, value.payment) == (None, None, None)


def _card(value: Any, case: str) -> None:
    assert isinstance(value, CardSupportSlotExtraction)
    if case == "normal":
        assert value.requested_action is not None
        assert value.block_reason_candidates
    else:
        assert value.requested_action is None
        assert value.card_hint is None


def _credit(value: Any, case: str) -> None:
    assert isinstance(value, CreditSlotExtraction)
    if case == "normal":
        assert value.product_of_interest is not None
        assert value.requested_amount is not None
    else:
        assert value == CreditSlotExtraction.model_validate(dict.fromkeys(CreditSlotExtraction.model_fields))


CHECKS: dict[str, Callable[[Any, str], None]] = {
    "dispute": _dispute,
    "account_inquiry": _account,
    "card_support": _card,
    "credit": _credit,
}


@pytest.mark.parametrize(
    "cassette", EXTRACTIONS, ids=lambda c: f"{c.labels['workflow']}-{c.language.value}-{c.labels['case']}"
)
async def test_extraction_cassettes_replay_and_fit_their_case(cassette: Cassette) -> None:
    value = await _replay(cassette)

    CHECKS[cassette.labels["workflow"]](value, cassette.labels["case"])


def test_every_workflow_in_the_registry_has_extraction_cassettes() -> None:
    assert {cassette.labels["workflow"] for cassette in EXTRACTIONS} == {str(w) for w in WORKFLOW_CATALOG.ids()}


def test_committed_cassette_files_are_canonical_json() -> None:
    for path, cassette in ALL:
        expected = json.dumps(cassette.model_dump(mode="json"), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        assert path.read_text(encoding="utf-8") == expected
