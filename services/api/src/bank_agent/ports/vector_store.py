"""Vector store port (ADR 0047): collections of points searched by cosine similarity with keyword filters."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.vectors import CollectionInfo, PayloadFilter, Vector, VectorMatch, VectorPoint


class VectorStore(Protocol):
    """A vector index. It is derived data: every collection can be rebuilt from its source, so it is never a
    system of record and is never backed up.

    Preconditions: collection names match ``COLLECTION_NAME_PATTERN``; every vector of a collection has its
    dimension. Filters come from application code (the session's language, jurisdiction, and, for any
    customer-scoped collection, the session's customer), never from model output.
    Postconditions: ``upsert`` is idempotent by point id; ``search`` returns at most ``limit`` matches that satisfy
    ``where``, best first by cosine similarity, ties broken by point id.
    Errors: ``VectorCollectionMissingError`` for a collection that does not exist, ``VectorStoreRejectedError`` for a
    request the store refuses (a dimension mismatch), ``VectorStoreError`` when the store is unreachable or fails.
    Isolation: the store applies ``where`` before ranking, so a match outside the filter is never returned.
    """

    def ensure_collection(self, name: str, *, dimension: int, keyword_fields: Sequence[str]) -> bool:
        """Create the cosine collection with keyword indexes on ``keyword_fields`` when it is missing.

        Returns ``True`` when it was created. An existing collection with another dimension is refused.
        """
        ...

    def collection(self, name: str) -> CollectionInfo | None:
        """The collection's dimension and point count, or ``None`` when it does not exist."""
        ...

    def list_collections(self) -> tuple[str, ...]:
        """Every collection name, sorted."""
        ...

    def upsert(self, name: str, points: Sequence[VectorPoint]) -> None:
        """Insert or replace points by id, durably, before returning."""
        ...

    def search(self, name: str, vector: Vector, *, limit: int, where: PayloadFilter) -> tuple[VectorMatch, ...]:
        """The best ``limit`` matches among the points that satisfy ``where``."""
        ...

    def delete_collection(self, name: str) -> bool:
        """Drop the collection; ``False`` when it did not exist."""
        ...
