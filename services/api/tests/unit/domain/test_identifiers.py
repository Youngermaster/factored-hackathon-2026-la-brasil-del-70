import pytest
from pydantic import BaseModel, ValidationError

from bank_agent.domain.identifiers import (
    CustomerId,
    IdempotencyKey,
    SourceRef,
    SourceTable,
    TraceId,
    TransactionId,
)


class _Holder(BaseModel):
    customer_id: CustomerId
    transaction_id: TransactionId | None = None
    key: IdempotencyKey | None = None
    trace: TraceId | None = None


def test_identifiers_are_plain_strings_at_runtime() -> None:
    assert CustomerId("C000123") == "C000123"
    assert _Holder(customer_id=CustomerId("C1")).customer_id == "C1"


@pytest.mark.parametrize(
    "fields",
    [
        {"customer_id": "has space"},
        {"customer_id": "-leading-dash"},
        {"customer_id": "C" * 21},
        {"customer_id": ""},
        {"customer_id": "C1", "transaction_id": "T" * 31},
        {"customer_id": "C1", "key": "short"},
        {"customer_id": "C1", "trace": "ABC"},
    ],
)
def test_rejects_malformed_identifiers(fields: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        _Holder.model_validate(fields)


def test_source_ref_round_trips_as_one_string() -> None:
    ref = SourceRef.model_validate("transactions:T000123")
    assert ref.table is SourceTable.TRANSACTIONS
    assert ref.key == "T000123"
    assert str(ref) == "transactions:T000123"
    assert ref.model_dump_json() == '"transactions:T000123"'
    assert SourceRef.of(SourceTable.POLICY_CLAUSES, "DSP-CO-2.1@3") == SourceRef.model_validate(
        "policy_clauses:DSP-CO-2.1@3"
    )


@pytest.mark.parametrize("value", ["transactions", "unknown_table:T1", "transactions:", "transactions:has space"])
def test_rejects_malformed_source_refs(value: str) -> None:
    with pytest.raises(ValidationError):
        SourceRef.model_validate(value)


def test_source_ref_schema_is_a_constrained_string() -> None:
    schema = SourceRef.model_json_schema(mode="serialization")
    assert schema["type"] == "string"
    assert schema["pattern"].startswith("^(customers|")
