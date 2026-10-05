"""Graceful degradation for retrievers with remote dependencies: BM25 answers when the primary one cannot.

The Qdrant retrievers depend on two services (the hosted embedding model and the vector store). When either fails,
times out, has its circuit open, or the collection is missing, this query is answered by the in-process BM25
retriever instead. The result names the retriever that served it (``retriever:bm25@1``), so the execution record
and the relevance threshold follow the fallback, and the counter ``bank.retrieval.fallbacks`` (attribute
``error.type``, the error code) shows how often it happened. A customer never sees the failure.
"""

from typing import Final

import structlog

from bank_agent.domain.errors import RetrievalBackendError
from bank_agent.domain.intelligence import ModelRef, RetrievalQuery, RetrievalResult
from bank_agent.ports.retrieval import Retriever
from bank_agent.ports.telemetry import Telemetry

FALLBACK_METRIC: Final = "bank.retrieval.fallbacks"
_log = structlog.get_logger(__name__)


class FallbackRetriever:
    """``Retriever`` decorator: ``primary``, or ``fallback`` when ``primary`` raises a ``RetrievalBackendError``."""

    def __init__(self, primary: Retriever, fallback: Retriever, *, telemetry: Telemetry, model: ModelRef) -> None:
        self._primary = primary
        self._fallback = fallback
        self._counter = telemetry.counter(FALLBACK_METRIC)
        self.model = model
        """The configured retriever, for reports; each result names the one that actually served it."""

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        try:
            return self._primary.search(query)
        except RetrievalBackendError as error:
            self._counter.add(1, {"error.type": error.code})
            _log.warning("retrieval_fallback", configured=str(self.model), error=error.code)
            return self._fallback.search(query)
