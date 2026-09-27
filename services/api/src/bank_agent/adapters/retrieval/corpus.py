"""The open-retrieval corpus: the current clauses of the policy pack, one document per clause and language.

Each document is the clause summary followed by its body, rendered with the clause's own parameters in the
locale of its language and jurisdiction, so figures such as ``90 días`` are searchable. ELG clauses are never
part of the corpus: eligibility answers come only from the synthetic eligibility service, so retrieved text can
never supply an eligibility rule. The index holds policy text only, never customer data.
"""

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.locale import Country, Language, Locale
from bank_agent.domain.policy import ClauseFamily, Jurisdiction, PolicyClause
from bank_agent.policy.explain import render_body
from bank_agent.ports.policy import PolicyRepository

EXCLUDED_FAMILIES = frozenset({ClauseFamily.ELG})
"""Families never indexed for open retrieval."""


@dataclass(frozen=True)
class ClauseDocument:
    clause_id: str
    version: int
    jurisdiction: Jurisdiction
    language: Language
    family: ClauseFamily
    text: str

    @property
    def ref(self) -> ClauseRef:
        return ClauseRef(clause_id=self.clause_id, version=self.version)

    @property
    def key(self) -> str:
        """Unique within a corpus: ``DSP-MX-1@1:es``."""
        return f"{self.clause_id}@{self.version}:{self.language.value}"

    def visible_to(self, language: Language, jurisdiction: Country) -> bool:
        """The filter every retriever applies before scoring: same language, the jurisdiction or ``ALL``."""
        return self.language is language and self.jurisdiction in {Jurisdiction(jurisdiction.value), Jurisdiction.ALL}


def document_locale(language: Language, jurisdiction: Jurisdiction) -> Locale:
    if language is Language.PT:
        return Locale.PT_BR
    if language is Language.EN:
        return Locale.EN_US
    if jurisdiction is Jurisdiction.ALL:
        return Locale.ES_MX
    return Country(jurisdiction.value).default_locale


def to_document(clause: PolicyClause) -> ClauseDocument:
    metadata = clause.metadata
    body = render_body(clause, document_locale(metadata.language, metadata.jurisdiction))
    return ClauseDocument(
        clause_id=metadata.clause_id,
        version=metadata.version,
        jurisdiction=metadata.jurisdiction,
        language=metadata.language,
        family=metadata.family,
        text=f"{metadata.summary}\n{body}",
    )


def build_corpus(repository: PolicyRepository) -> tuple[ClauseDocument, ...]:
    """Every current clause in every language, except the excluded families, sorted by key."""
    documents = (to_document(clause) for clause in repository.list_clauses())
    return tuple(sorted((d for d in documents if d.family not in EXCLUDED_FAMILIES), key=lambda d: d.key))


def corpus_digest(documents: Iterable[ClauseDocument]) -> str:
    """SHA-256 over every document's key and text, in key order."""
    digest = hashlib.sha256()
    for document in sorted(documents, key=lambda d: d.key):
        digest.update(f"{document.key}\n{document.text}\n".encode())
    return digest.hexdigest()
