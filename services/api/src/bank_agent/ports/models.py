"""Ports for the replaceable learned and rule-based components."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from bank_agent.domain.base import UntrustedText
from bank_agent.domain.intelligence import (
    IntentPrediction,
    LanguageDetection,
    ResolvedArtifact,
    TransactionDescriptor,
    TransactionResolution,
)
from bank_agent.domain.locale import Language
from bank_agent.domain.transaction import Transaction


class IntentRouter(Protocol):
    """Classifies a customer message into an intent.

    Preconditions: ``text`` is non-empty customer text, treated as data.
    Postconditions: returns a prediction whose ``model`` names the concrete version, with ``below_threshold``
    computed from the threshold stored with the model artifact.
    Errors: none for ordinary input; empty text is a programming error.
    Isolation: receives only the message text and language, never identifiers.
    """

    def route(self, text: UntrustedText, language: Language) -> IntentPrediction:
        """Return the predicted intent for ``text``."""
        ...


class TransactionResolver(Protocol):
    """Ranks candidate transactions against what the customer described.

    Preconditions: ``candidates`` are the session customer's own transactions, fetched by the application
    through a context-bound repository.
    Postconditions: every ranked id is one of the candidates, each at most once; ``clear_winner`` is set only
    when the top candidate beats the runner-up by the model's margin.
    Errors: none for ordinary input; no candidates yields an empty ranking.
    Isolation: the resolver never fetches data, so it cannot reach another customer's transactions.
    """

    def rank(
        self, descriptor: TransactionDescriptor, candidates: Sequence[Transaction], *, now: datetime
    ) -> TransactionResolution:
        """Return the candidates ranked best first."""
        ...


class LanguageDetector(Protocol):
    """Detects the language of a customer message.

    Preconditions: ``text`` is non-empty customer text, treated as data.
    Postconditions: ``language`` is ``None`` when the detector is uncertain, and ``is_mixed`` is true for
    code-switched input.
    Errors: none for ordinary input.
    Isolation: receives only the text.
    """

    def detect(self, text: UntrustedText) -> LanguageDetection:
        """Return the detected language of ``text``."""
        ...


class ModelRegistry(Protocol):
    """Resolves model artifacts by name and version or alias (``champion``, ``candidate``).

    Preconditions: called at startup or when settings select a model, never per turn.
    Postconditions: the result names the concrete version, a local path, and the artifact's SHA-256 digest.
    Errors: ``ModelArtifactNotFoundError`` for an unknown name, version, or alias;
    ``ModelArtifactIntegrityError`` when the stored digest does not match the file.
    Isolation: artifacts contain model parameters only, never customer records.
    """

    def resolve(self, name: str, version_or_alias: str) -> ResolvedArtifact:
        """Return the artifact for ``name`` at ``version_or_alias``."""
        ...
