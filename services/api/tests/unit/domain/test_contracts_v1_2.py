"""Contract version 1.2.0: the retrieval record on execution records and the ``list_my_cards`` tool name."""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from bank_agent.domain.actions import ToolName
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.execution_record import (
    ExecutionRecord,
    RetrievalDecisionCode,
    RetrievalRecord,
    ToolCallRecord,
    ToolCallStatus,
)
from bank_agent.domain.intelligence import ModelRef
from bank_agent_builders import execution_record

SCHEMAS = Path(__file__).resolve().parents[5] / "contracts" / "schemas"
BM25 = ModelRef.model_validate("retriever:bm25@1")


def _fits(document: dict[str, Any]) -> None:
    schema = json.loads((SCHEMAS / "execution_record.v1.json").read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(document)) == []


def test_a_record_carries_the_retrieval_decision_threshold_and_score() -> None:
    retrieval = RetrievalRecord(
        retriever=BM25,
        decision=RetrievalDecisionCode.ANSWER,
        threshold=3.6292,
        top_score=5.1,
        citations=(ClauseRef.parse("DSP-MX-1@1"),),
    )
    record = execution_record(retrieval=retrieval)
    assert record.schema_version == "1.2.0"
    assert ExecutionRecord.model_validate_json(record.model_dump_json()) == record
    _fits(record.model_dump(mode="json"))


def test_an_answer_needs_citations_and_an_abstention_has_none() -> None:
    with pytest.raises(ValidationError, match="cites at least one clause"):
        RetrievalRecord(retriever=BM25, decision=RetrievalDecisionCode.ANSWER, threshold=1.0)
    with pytest.raises(ValidationError, match="cites no clause"):
        RetrievalRecord(
            retriever=BM25,
            decision=RetrievalDecisionCode.ABSTAIN,
            threshold=1.0,
            citations=(ClauseRef.parse("DSP-MX-1@1"),),
        )


def test_a_1_1_record_cannot_carry_the_retrieval_record() -> None:
    abstain = RetrievalRecord(retriever=BM25, decision=RetrievalDecisionCode.ABSTAIN, threshold=1.0, top_score=0.2)
    with pytest.raises(ValidationError, match=r"added in 1\.2\.0"):
        execution_record(schema_version="1.1.0", retrieval=abstain)


def test_the_card_listing_tool_fits_the_schema() -> None:
    call = ToolCallRecord(sequence=1, tool=ToolName.LIST_MY_CARDS, status=ToolCallStatus.OK, latency_ms=3)
    _fits(execution_record(tool_calls=(call,)).model_dump(mode="json"))


def test_only_the_retrieval_record_is_added_in_1_2() -> None:
    schema = json.loads((SCHEMAS / "execution_record.v1.json").read_text(encoding="utf-8"))
    added = {key for key, value in schema["properties"].items() if value.get("x-added-in") == "1.2.0"}
    assert added == {"retrieval"}
