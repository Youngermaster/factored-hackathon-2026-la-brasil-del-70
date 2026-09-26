"""Shared building blocks for domain models: the base model, field markers, and common field types.

Every domain model is immutable and rejects unknown keys. Entities change by returning a new instance.
Two marker objects annotate fields for the layers that must treat them specially:

- ``Pii(kind)`` marks personal data. The JSON Schema carries ``x-pii``. Redaction (phase 08), response DTO
  tests (phase 11), and evaluation graders (phase 14) find these fields with ``pii_fields``.
- ``Internal()`` marks data that is never shown to customers or sent to a model, such as fraud labels. The
  JSON Schema carries ``x-internal``, and ``internal_fields`` finds them.
"""

import types
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, NewType, Self, Union, get_args, get_origin

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    GetJsonSchemaHandler,
    StringConstraints,
)
from pydantic_core import CoreSchema


class DomainModel(BaseModel):
    """Base class for every domain model: frozen, and unknown keys are rejected.

    In serialization-mode JSON Schemas every field is required, because a serialized document always carries
    every field, defaults included; consumers can rely on that.
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", validate_default=True, json_schema_serialization_defaults_required=True
    )

    def evolve(self, **changes: Any) -> Self:
        """Return a copy with ``changes`` applied and every validator run again.

        Unlike ``model_copy(update=...)``, which skips validation, this keeps invariants intact.
        """
        data = dict(self)
        data.update(changes)
        return type(self).model_validate(data)


@dataclass(frozen=True, slots=True)
class Pii:
    """Field marker for personal data. ``kind`` names the category, for example ``name`` or ``free_text``."""

    kind: str

    def __get_pydantic_json_schema__(self, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> dict[str, Any]:
        schema = dict(handler(core_schema))
        schema["x-pii"] = self.kind
        return schema


@dataclass(frozen=True, slots=True)
class Internal:
    """Field marker for data that is never rendered to customers or sent to a language model."""

    def __get_pydantic_json_schema__(self, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> dict[str, Any]:
        schema = dict(handler(core_schema))
        schema["x-internal"] = True
        return schema


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]
"""A timezone-aware instant, normalized to UTC. Naive datetimes are rejected."""

UntrustedText = NewType("UntrustedText", str)
"""Text written by a customer or stored in a record (for example ``merchant_name``).

It is data, never instructions. Prompt builders must wrap it in data delimiters. The nominal type makes mypy
reject a bare ``str`` where untrusted text is expected, and the reverse.
"""

_NO_CONTROL_CHARACTERS = r"^[^\x00-\x1F\x7F]*$"

Code = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
"""A stable machine-readable code in snake case, such as a reason code or an error code."""

SingleLineText = Annotated[str, StringConstraints(min_length=1, max_length=300, pattern=_NO_CONTROL_CHARACTERS)]
"""Short free text on one line: no line breaks or other control characters, at most 300 characters."""

SummaryText = Annotated[str, StringConstraints(min_length=1, max_length=500, pattern=_NO_CONTROL_CHARACTERS)]
"""A single-paragraph summary of at most 500 characters. Line breaks are rejected, so a transcript cannot be pasted."""


def _is_marked(metadata: list[Any], marker_type: type[Any]) -> Any | None:
    for item in metadata:
        if isinstance(item, marker_type):
            return item
    return None


def _nested_models(annotation: Any) -> list[type[BaseModel]]:
    """Return every ``BaseModel`` subclass referenced by ``annotation`` (through unions, tuples, and dicts)."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    found: list[type[BaseModel]] = []
    origin = get_origin(annotation)
    if origin is Annotated:
        return _nested_models(get_args(annotation)[0])
    if origin is not None:
        for argument in get_args(annotation):
            found.extend(_nested_models(argument))
    return found


def _marked_metadata(annotation: Any, marker_type: type[Any]) -> Any | None:
    """Find a marker inside ``Annotated`` wrappers nested in an optional union."""
    origin = get_origin(annotation)
    if origin is Annotated:
        marker = _is_marked(list(get_args(annotation)[1:]), marker_type)
        if marker is not None:
            return marker
        return _marked_metadata(get_args(annotation)[0], marker_type)
    if origin in (Union, types.UnionType):
        for argument in get_args(annotation):
            marker = _marked_metadata(argument, marker_type)
            if marker is not None:
                return marker
    return None


def _collect(model: type[BaseModel], marker_type: type[Any], prefix: str, seen: set[type[BaseModel]]) -> dict[str, Any]:
    if model in seen:
        return {}
    seen = seen | {model}
    result: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        path = f"{prefix}{name}"
        marker = _is_marked(field.metadata, marker_type) or _marked_metadata(field.annotation, marker_type)
        if marker is not None:
            result[path] = marker
        for nested in _nested_models(field.annotation):
            result.update(_collect(nested, marker_type, f"{path}.", seen))
    return result


def pii_fields(model: type[BaseModel]) -> dict[str, str]:
    """Map the dotted path of every personal-data field in ``model`` (including nested models) to its kind."""
    return {path: marker.kind for path, marker in _collect(model, Pii, "", set()).items()}


def internal_fields(model: type[BaseModel]) -> frozenset[str]:
    """Return the dotted paths of every internal-only field in ``model``, including nested models."""
    return frozenset(_collect(model, Internal, "", set()))
