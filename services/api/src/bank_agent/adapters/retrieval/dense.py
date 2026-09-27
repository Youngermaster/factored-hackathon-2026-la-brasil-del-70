"""Dense retrieval: cosine similarity between the query embedding and the stored passage embeddings."""

import re
from collections.abc import Sequence

from bank_agent.adapters.retrieval.corpus import ClauseDocument
from bank_agent.adapters.retrieval.embedding import Embedder, Vector, dot
from bank_agent.adapters.retrieval.ranking import rank_hits
from bank_agent.domain.errors import RetrievalIndexError
from bank_agent.domain.intelligence import ModelComponent, ModelRef, RetrievalQuery, RetrievalResult

DENSE_MODEL_NAME = "dense"


def model_version(model_id: str) -> str:
    """A ``ModelRef`` version from an embedding model id: ``intfloat/multilingual-e5-small`` gives
    ``intfloat.multilingual-e5-small``."""
    name = model_id.split("|", 1)[0]
    return re.sub(r"[^A-Za-z0-9._-]", ".", name).strip(".-_")[:64] or "unknown"


class DenseIndex:
    """One unit vector per document, all produced by the same embedding model."""

    def __init__(self, documents: Sequence[ClauseDocument], vectors: Sequence[Vector], model_id: str) -> None:
        if len(documents) != len(vectors):
            raise RetrievalIndexError("the dense index needs one vector per document")
        self.documents = tuple(documents)
        self.vectors = tuple(vectors)
        self.model_id = model_id

    @classmethod
    def build(cls, documents: Sequence[ClauseDocument], embedder: Embedder) -> "DenseIndex":
        return cls(documents, embedder.embed_passages([d.text for d in documents]), embedder.model_id)


class DenseRetriever:
    """``Retriever`` over a dense index; the embedder must be the model that built the index."""

    def __init__(self, index: DenseIndex, embedder: Embedder) -> None:
        if embedder.model_id != index.model_id:
            raise RetrievalIndexError("the dense index was built with another embedding model")
        self.index = index
        self._embedder = embedder
        self.model = ModelRef(
            component=ModelComponent.RETRIEVER, name=DENSE_MODEL_NAME, version=model_version(index.model_id)
        )

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        visible = [
            (document, vector)
            for document, vector in zip(self.index.documents, self.index.vectors, strict=True)
            if document.visible_to(query.language, query.jurisdiction)
        ]
        if not visible:
            return RetrievalResult(hits=(), retriever=self.model)
        embedded = self._embedder.embed_query(query.text)
        scored = ((document, dot(embedded, vector)) for document, vector in visible)
        return RetrievalResult(hits=rank_hits(scored, query.k), retriever=self.model)
