"""An in-memory ``VectorStore``: exact cosine search over every point, for unit tests and offline evaluation.

It follows the same contract as the Qdrant adapter (the shared suite in ``tests/contracts`` runs against both), so
an evaluation over it measures the same ranking a Qdrant collection of this size returns: Qdrant searches a
collection this small exactly, without the approximate HNSW graph.
"""

import math
import threading
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from bank_agent.domain.errors import VectorCollectionMissingError, VectorStoreRejectedError
from bank_agent.domain.vectors import CollectionInfo, PayloadFilter, PayloadValue, Vector, VectorMatch, VectorPoint


def _unit(vector: Sequence[float]) -> Vector:
    norm = math.sqrt(sum(value * value for value in vector))
    return tuple(value / norm for value in vector) if norm > 0.0 else tuple(0.0 for _ in vector)


@dataclass
class _Collection:
    dimension: int
    keyword_fields: tuple[str, ...]
    points: dict[uuid.UUID, tuple[Vector, dict[str, PayloadValue]]] = field(default_factory=dict)


class InMemoryVectorStore:
    """Thread-safe: the retriever runs in worker threads."""

    def __init__(self) -> None:
        self._collections: dict[str, _Collection] = {}
        self._lock = threading.Lock()

    def _get(self, name: str) -> _Collection:
        found = self._collections.get(name)
        if found is None:
            raise VectorCollectionMissingError(f"collection {name} does not exist")
        return found

    def ensure_collection(self, name: str, *, dimension: int, keyword_fields: Sequence[str]) -> bool:
        if dimension < 1:
            raise VectorStoreRejectedError("a collection needs a positive dimension")
        with self._lock:
            existing = self._collections.get(name)
            if existing is not None:
                if existing.dimension != dimension:
                    raise VectorStoreRejectedError(
                        f"collection {name} has dimension {existing.dimension}, not {dimension}"
                    )
                return False
            self._collections[name] = _Collection(dimension, tuple(keyword_fields))
            return True

    def collection(self, name: str) -> CollectionInfo | None:
        with self._lock:
            found = self._collections.get(name)
            if found is None:
                return None
            return CollectionInfo(name=name, dimension=found.dimension, points=len(found.points))

    def list_collections(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._collections))

    def upsert(self, name: str, points: Sequence[VectorPoint]) -> None:
        with self._lock:
            target = self._get(name)
            for point in points:
                if len(point.vector) != target.dimension:
                    raise VectorStoreRejectedError(
                        f"a point has dimension {len(point.vector)}; collection {name} has {target.dimension}"
                    )
            for point in points:
                target.points[point.id] = (_unit(point.vector), dict(point.payload))

    def search(self, name: str, vector: Vector, *, limit: int, where: PayloadFilter) -> tuple[VectorMatch, ...]:
        if limit < 1:
            raise VectorStoreRejectedError("the search limit must be positive")
        with self._lock:
            target = self._get(name)
            if len(vector) != target.dimension:
                raise VectorStoreRejectedError(
                    f"the query has dimension {len(vector)}; collection {name} has {target.dimension}"
                )
            candidates = [(key, stored, payload) for key, (stored, payload) in target.points.items()]
        query = _unit(vector)
        scored = [
            (sum(a * b for a, b in zip(query, stored, strict=True)), key, payload)
            for key, stored, payload in candidates
            if where.matches(payload)
        ]
        scored.sort(key=lambda item: (-item[0], str(item[1])))
        return tuple(VectorMatch(id=key, score=score, payload=payload) for score, key, payload in scored[:limit])

    def delete_collection(self, name: str) -> bool:
        with self._lock:
            return self._collections.pop(name, None) is not None
