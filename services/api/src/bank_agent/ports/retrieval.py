"""Retriever port (phase 07)."""

from typing import Protocol

from bank_agent.domain.intelligence import RetrievalQuery, RetrievalResult


class Retriever(Protocol):
    """Open retrieval over policy clauses, used only for informational questions.

    Preconditions: the query's jurisdiction comes from the verified customer profile.
    Postconditions: hits are filtered by ``query.language`` and ``query.jurisdiction`` (plus ``ALL``) before
    scoring, ranked best first, at most ``query.k``. Abstention below a relevance threshold is applied by the
    caller's retrieval policy, not here.
    Errors: none beyond programming errors; an empty index returns no hits.
    Isolation: the index holds policy text only, never customer data.
    """

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        """Return scored clause references for the query."""
        ...
