"""Value objects of the vector store port (ADR 0047): points, filters, matches, and collection facts.

A point is an id, a vector, and a flat payload of keyword values. The store measures cosine similarity, so a
match score is in ``[-1, 1]`` whatever the vector norms. Filters are conjunctions of keyword matches; there is no
free-form query language, so nothing a model writes can become a filter.
"""

import re
import uuid
from typing import Annotated, Final

from pydantic import Field, StringConstraints

from bank_agent.domain.base import DomainModel

Vector = tuple[float, ...]
"""An embedding. Adapters normalize it where the measure needs a unit vector."""

PayloadValue = str | int
PAYLOAD_KEY_PATTERN: Final = r"^[a-z][a-z0-9_]{0,63}$"
COLLECTION_NAME_PATTERN: Final = r"^[a-z0-9][a-z0-9_-]{0,127}$"
MAX_DIMENSION: Final = 4096
PayloadKey = Annotated[str, StringConstraints(pattern=PAYLOAD_KEY_PATTERN)]
CollectionName = Annotated[str, StringConstraints(pattern=COLLECTION_NAME_PATTERN)]


def collection_slug(text: str, *, max_length: int = 48) -> str:
    """A lowercase slug usable in a collection name: ``azure/text-embedding-3-small`` gives
    ``azure-text-embedding-3-small``."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_length].strip("-") or "x"


class VectorPoint(DomainModel):
    id: uuid.UUID
    vector: Annotated[Vector, Field(min_length=1, max_length=MAX_DIMENSION)]
    payload: dict[PayloadKey, PayloadValue]


class FieldMatch(DomainModel):
    """The payload field ``key`` equals one of ``any_of``."""

    key: PayloadKey
    any_of: Annotated[tuple[PayloadValue, ...], Field(min_length=1, max_length=32)]


class PayloadFilter(DomainModel):
    """Every condition must hold (a conjunction)."""

    must: tuple[FieldMatch, ...] = ()

    def matches(self, payload: dict[str, PayloadValue]) -> bool:
        return all(payload.get(condition.key) in condition.any_of for condition in self.must)


class VectorMatch(DomainModel):
    id: uuid.UUID
    score: Annotated[float, Field(allow_inf_nan=False)]
    payload: dict[PayloadKey, PayloadValue]


class CollectionInfo(DomainModel):
    name: CollectionName
    dimension: Annotated[int, Field(ge=1, le=MAX_DIMENSION)]
    points: Annotated[int, Field(ge=0)]
