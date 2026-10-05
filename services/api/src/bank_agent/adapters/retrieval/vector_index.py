"""The policy clauses in a vector store collection, and the retriever over it (ADR 0047).

One collection per policy pack version and embedding model, so a new pack or a new model never mixes with an old
index: ``policy-clauses-<pack slug>-<model slug>``. Each clause document (one per clause, version, and language) is
one point whose id is a UUID v5 of its key (``DSP-MX-1@1:es``), so indexing twice writes the same points. The
payload holds keyword fields only (clause id, version, language, jurisdiction, family, workflow), never the clause
text: the pack stays the source of truth and citations are resolved from it. Searches filter by the query's language
and jurisdiction (plus ``ALL``), both set by application code from the verified session, never by a model.

The index holds synthetic policy text only. No collection is customer-scoped; one that is would add the session's
customer as a mandatory filter here, from the session context, never from a model-supplied value.
"""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from bank_agent.adapters.retrieval.corpus import ClauseDocument
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.errors import VectorCollectionMissingError, VectorStoreError
from bank_agent.domain.intelligence import ModelComponent, ModelRef, RetrievalHit, RetrievalQuery, RetrievalResult
from bank_agent.domain.policy import ClauseFamily, Jurisdiction
from bank_agent.domain.vectors import FieldMatch, PayloadFilter, VectorMatch, VectorPoint, collection_slug
from bank_agent.ports.embeddings import Embedder
from bank_agent.ports.vector_store import VectorStore

QDRANT_MODEL_NAME: Final = "qdrant"
COLLECTION_PREFIX: Final = "policy-clauses"
POINT_NAMESPACE: Final = uuid.UUID("6b1f3c1e-2f4a-5d7e-9a10-0c4e8d2b7a47")
"""Fixed namespace for point ids: changing it re-keys every point, so it never changes."""
KEYWORD_FIELDS: Final = ("language", "jurisdiction", "workflow", "family", "clause_id")
FAMILY_WORKFLOW: Final = {
    ClauseFamily.ACC: "account_inquiry",
    ClauseFamily.CRD: "card_support",
    ClauseFamily.DSP: "dispute",
    ClauseFamily.CRE: "credit",
}
"""Families that belong to one workflow; every other family (scope, privacy, escalation, ...) is ``shared``."""
SHARED_WORKFLOW: Final = "shared"


def model_version(model_id: str) -> str:
    """A ``ModelRef`` version from an embedding model id with its dimension: ``azure/text-embedding-3-small|512``
    gives ``azure.text-embedding-3-small.512``."""
    return re.sub(r"[^A-Za-z0-9._-]+", ".", model_id).strip(".-_")[:64] or "unknown"


def collection_name(pack_version: str, model_id: str) -> str:
    return f"{COLLECTION_PREFIX}-{collection_slug(pack_version, max_length=40)}-{collection_slug(model_id)}"


def point_id(document: ClauseDocument) -> uuid.UUID:
    return uuid.uuid5(POINT_NAMESPACE, document.key)


def workflow_of(family: ClauseFamily) -> str:
    return FAMILY_WORKFLOW.get(family, SHARED_WORKFLOW)


def to_point(document: ClauseDocument, vector: tuple[float, ...]) -> VectorPoint:
    return VectorPoint(
        id=point_id(document),
        vector=vector,
        payload={
            "clause_id": document.clause_id,
            "version": document.version,
            "language": document.language.value,
            "jurisdiction": document.jurisdiction.value,
            "family": document.family.value,
            "workflow": workflow_of(document.family),
        },
    )


@dataclass(frozen=True)
class IndexReport:
    collection: str
    created: bool
    points: int
    model_id: str


class VectorClauseIndex:
    """The clause collection for one pack version and one embedding model."""

    def __init__(self, store: VectorStore, embedder: Embedder, *, pack_version: str) -> None:
        self._store = store
        self._embedder = embedder
        self.name = collection_name(pack_version, embedder.model_id)

    def build(self, documents: Sequence[ClauseDocument]) -> IndexReport:
        """Embed every document and upsert it. Idempotent: the point ids are deterministic, so a second run
        rewrites the same points; a collection with points of another pack is impossible by its name."""
        if not documents:
            raise VectorStoreError("there are no documents to index")
        vectors = self._embedder.embed_passages([document.text for document in documents])
        created = self._store.ensure_collection(self.name, dimension=len(vectors[0]), keyword_fields=KEYWORD_FIELDS)
        self._store.upsert(self.name, [to_point(d, v) for d, v in zip(documents, vectors, strict=True)])
        points = self.check(len(documents))
        return IndexReport(collection=self.name, created=created, points=points, model_id=self._embedder.model_id)

    def check(self, expected_points: int) -> int:
        """The point count, or ``VectorCollectionMissingError`` when the collection is missing or incomplete."""
        info = self._store.collection(self.name)
        if info is None:
            raise VectorCollectionMissingError(f"collection {self.name} does not exist; run bank-agent index qdrant")
        if info.points != expected_points:
            raise VectorCollectionMissingError(
                f"collection {self.name} has {info.points} points, not {expected_points}; run bank-agent index qdrant"
            )
        return info.points


def _hit_key(match: VectorMatch) -> tuple[float, str, int]:
    clause_id, version = match.payload.get("clause_id"), match.payload.get("version")
    if not isinstance(clause_id, str) or not isinstance(version, int):
        raise VectorStoreError("a vector match has no clause id or version in its payload")
    return -match.score, clause_id, version


class VectorRetriever:
    """``Retriever`` over a clause collection: embed the query, search with the language and jurisdiction filter.

    Errors: the ``RetrievalBackendError`` family (embedding or vector store failures, a missing collection), which
    ``FallbackRetriever`` turns into a BM25 answer.
    """

    def __init__(self, store: VectorStore, embedder: Embedder, *, collection: str) -> None:
        self._store = store
        self._embedder = embedder
        self.collection = collection
        self.model = ModelRef(
            component=ModelComponent.RETRIEVER, name=QDRANT_MODEL_NAME, version=model_version(embedder.model_id)
        )

    @staticmethod
    def where(query: RetrievalQuery) -> PayloadFilter:
        return PayloadFilter(
            must=(
                FieldMatch(key="language", any_of=(query.language.value,)),
                FieldMatch(key="jurisdiction", any_of=(query.jurisdiction.value, Jurisdiction.ALL.value)),
            )
        )

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        vector = self._embedder.embed_query(query.text)
        matches = self._store.search(self.collection, vector, limit=query.k, where=self.where(query))
        ordered = sorted(_hit_key(match) for match in matches)[: query.k]
        hits = tuple(
            RetrievalHit(clause=ClauseRef(clause_id=clause_id, version=version), score=-negative, rank=rank)
            for rank, (negative, clause_id, version) in enumerate(ordered, 1)
        )
        return RetrievalResult(hits=hits, retriever=self.model)
