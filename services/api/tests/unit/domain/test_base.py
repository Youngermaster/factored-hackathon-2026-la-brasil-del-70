from typing import Annotated

import pytest
from pydantic import BaseModel, ValidationError

from bank_agent.domain.base import DomainModel, Internal, Pii, internal_fields, pii_fields
from bank_agent.domain.customer import Customer
from bank_agent.domain.handoff import HandoffRecord
from bank_agent.domain.identity import DocumentIdentification
from bank_agent.domain.transaction import Transaction


class _Inner(DomainModel):
    hidden: Annotated[str, Internal()]
    email: Annotated[str, Pii("email")] | None = None


class _Outer(DomainModel):
    name: Annotated[str, Pii("name")]
    inner: _Inner
    items: tuple[_Inner, ...] = ()
    mapping: dict[str, _Inner] = {}  # noqa: RUF012


def test_finds_markers_through_nested_models_optionals_and_containers() -> None:
    assert pii_fields(_Outer) == {
        "name": "name",
        "inner.email": "email",
        "items.email": "email",
        "mapping.email": "email",
    }
    assert internal_fields(_Outer) == frozenset({"inner.hidden", "items.hidden", "mapping.hidden"})


def test_markers_on_real_models() -> None:
    assert pii_fields(Customer) == {"first_name": "name"}
    assert internal_fields(Transaction) == frozenset({"fraud"})
    assert pii_fields(DocumentIdentification) == {"document_number": "document_number", "phone_last4": "phone"}
    assert pii_fields(HandoffRecord) == {"resolution.note": "free_text"}


def test_markers_appear_in_the_json_schema() -> None:
    schema = _Outer.model_json_schema()
    assert schema["properties"]["name"]["x-pii"] == "name"
    assert schema["$defs"]["_Inner"]["properties"]["hidden"]["x-internal"] is True


def test_models_are_frozen_and_reject_unknown_keys() -> None:
    inner = _Inner(hidden="s")
    with pytest.raises(ValidationError):
        inner.hidden = "t"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        _Inner.model_validate({"hidden": "s", "extra": 1})


def test_evolve_revalidates() -> None:
    class Positive(DomainModel):
        value: Annotated[int, "doc"]

        def model_post_init(self, context: object, /) -> None:
            if self.value < 0:
                raise ValueError("negative")

    assert Positive(value=1).evolve(value=2).value == 2
    with pytest.raises(ValidationError):
        Positive(value=1).evolve(value="not a number")


def test_plain_models_have_no_markers() -> None:
    class Plain(BaseModel):
        value: int

    assert pii_fields(Plain) == {}
