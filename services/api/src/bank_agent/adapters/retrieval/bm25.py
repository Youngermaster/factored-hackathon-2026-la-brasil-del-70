"""Okapi BM25 over the clause corpus, with statistics per language.

Implemented here rather than taken from a library: ``rank-bm25`` has had no release since 2022, and ``bm25s``
brings SciPy into the API runtime for a corpus of about 140 short documents. The scoring is the standard one,
with the non-negative inverse document frequency ``ln(1 + (N - df + 0.5) / (df + 0.5))`` computed over the
documents of the query's language. Each distinct query term counts once.
"""

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bank_agent.adapters.retrieval.corpus import ClauseDocument
from bank_agent.adapters.retrieval.ranking import rank_hits
from bank_agent.adapters.retrieval.text import tokenize
from bank_agent.domain.errors import RetrievalIndexError
from bank_agent.domain.intelligence import ModelComponent, ModelRef, RetrievalQuery, RetrievalResult
from bank_agent.domain.locale import Language

BM25_MODEL = ModelRef(component=ModelComponent.RETRIEVER, name="bm25", version="1")


@dataclass(frozen=True)
class Bm25Parameters:
    k1: float = 1.2
    b: float = 0.75


class Bm25Index:
    """Term counts per document plus document frequencies and average lengths per language."""

    def __init__(
        self,
        documents: Sequence[ClauseDocument],
        term_counts: Sequence[Mapping[str, int]],
        parameters: Bm25Parameters = Bm25Parameters(),  # noqa: B008 - frozen dataclass, safe as a default
    ) -> None:
        if len(documents) != len(term_counts):
            raise RetrievalIndexError("the BM25 index needs one term count table per document")
        self.documents = tuple(documents)
        self.parameters = parameters
        self._counts = tuple(dict(counts) for counts in term_counts)
        self._lengths = tuple(sum(counts.values()) for counts in self._counts)
        self._df: dict[Language, Counter[str]] = {}
        self._size: Counter[Language] = Counter()
        total_length: Counter[Language] = Counter()
        for document, counts, length in zip(self.documents, self._counts, self._lengths, strict=True):
            self._df.setdefault(document.language, Counter()).update(counts.keys())
            self._size[document.language] += 1
            total_length[document.language] += length
        self._average = {language: total_length[language] / size for language, size in self._size.items()}

    @classmethod
    def build(cls, documents: Sequence[ClauseDocument], parameters: Bm25Parameters = Bm25Parameters()) -> "Bm25Index":  # noqa: B008
        counts = [Counter(tokenize(document.text, document.language)) for document in documents]
        return cls(documents, counts, parameters)

    def idf(self, language: Language, term: str) -> float:
        size = self._size[language]
        frequency = self._df.get(language, Counter())[term]
        return math.log(1.0 + (size - frequency + 0.5) / (frequency + 0.5))

    def score(self, position: int, terms: Sequence[str]) -> float:
        document = self.documents[position]
        counts, length = self._counts[position], self._lengths[position]
        k1, b = self.parameters.k1, self.parameters.b
        norm = k1 * (1.0 - b + b * length / self._average[document.language])
        total = 0.0
        for term in dict.fromkeys(terms):
            frequency = counts.get(term, 0)
            if frequency:
                total += self.idf(document.language, term) * frequency * (k1 + 1.0) / (frequency + norm)
        return total

    def to_payload(self) -> dict[str, Any]:
        return {
            "parameters": {"k1": self.parameters.k1, "b": self.parameters.b},
            "documents": [document.key for document in self.documents],
            "term_counts": [dict(sorted(counts.items())) for counts in self._counts],
        }

    @classmethod
    def from_payload(cls, documents: Sequence[ClauseDocument], payload: Mapping[str, Any]) -> "Bm25Index":
        """Rebuild a stored index; the stored document keys must be exactly the current corpus, in order."""
        if payload.get("documents") != [document.key for document in documents]:
            raise RetrievalIndexError("the stored BM25 index was built for another corpus")
        parameters = Bm25Parameters(**payload["parameters"])
        return cls(documents, payload["term_counts"], parameters)


class Bm25Retriever:
    """``Retriever`` over a BM25 index: filters by language and jurisdiction, then scores; zero scores drop out."""

    def __init__(self, index: Bm25Index) -> None:
        self.index = index
        self.model = BM25_MODEL

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        terms = tokenize(query.text, query.language)
        scored = (
            (document, self.index.score(position, terms))
            for position, document in enumerate(self.index.documents)
            if document.visible_to(query.language, query.jurisdiction)
        )
        return RetrievalResult(hits=rank_hits(((d, s) for d, s in scored if s > 0.0), query.k), retriever=self.model)
