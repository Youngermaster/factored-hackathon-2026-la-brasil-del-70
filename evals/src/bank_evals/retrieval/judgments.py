"""Relevance judgments for open retrieval (``evals/data/retrieval_judgments.v1.jsonl``).

Each line is one team-written query with its language, locale, jurisdiction, workflow, graded relevant clauses,
the expected behavior (answer or abstain), a split (``dev`` tunes thresholds, ``test`` reports), its provenance,
and its review status. The labeling protocol is ``docs/evaluation/retrieval-labeling.md``.
"""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

from bank_agent.domain.decision import CLAUSE_ID_PATTERN
from bank_agent.domain.locale import Country, Language, Locale

JudgmentWorkflow = Literal["account_inquiry", "card_support", "dispute", "credit", "out_of_scope"]
Split = Literal["dev", "test"]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_JUDGMENTS = REPOSITORY_ROOT / "evals" / "data" / "retrieval_judgments.v1.jsonl"


class RelevantClause(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    clause_id: Annotated[str, StringConstraints(pattern=CLAUSE_ID_PATTERN)]
    grade: Annotated[int, Field(ge=1, le=3)]
    """3 fully answers, 2 governs the question (the default for the main clause), 1 related and useful."""


class Judgment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: Annotated[str, StringConstraints(pattern=r"^[a-z]{3}-[0-9]{2,3}$")]
    workflow: JudgmentWorkflow
    query: Annotated[str, StringConstraints(min_length=3, max_length=500)]
    language: Language
    locale: Locale
    jurisdiction: Country
    relevant: tuple[RelevantClause, ...]
    expected: Literal["answer", "abstain"]
    split: Split
    provenance: Literal["team_generated"]
    review_status: Literal["pending", "reviewed", "rejected"]
    notes: Annotated[str, StringConstraints(max_length=500)] | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.locale.language is not self.language:
            raise ValueError("the locale must be in the judgment's language")
        if (self.expected == "abstain") != (not self.relevant):
            raise ValueError("an abstention has no relevant clause, and an answer has at least one")
        if (self.workflow == "out_of_scope") != (self.expected == "abstain"):
            raise ValueError("exactly the out-of-scope queries expect abstention")
        ids = [item.clause_id for item in self.relevant]
        if len(ids) != len(set(ids)):
            raise ValueError("a clause is listed once per judgment")
        return self

    @property
    def grades(self) -> dict[str, int]:
        return {item.clause_id: item.grade for item in self.relevant}


class JudgmentsError(ValueError):
    """The judgments file is malformed; the message names the line, never the query text."""


def load_judgments(path: Path = DEFAULT_JUDGMENTS) -> tuple[Judgment, ...]:
    judgments: list[Judgment] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            judgments.append(Judgment.model_validate(json.loads(line)))
        except (ValueError, ValidationError) as error:
            raise JudgmentsError(f"line {number} of {path.name} is not a valid judgment") from error
    ids = [judgment.query_id for judgment in judgments]
    if len(ids) != len(set(ids)):
        raise JudgmentsError(f"{path.name} repeats a query id")
    return tuple(judgments)


def judgments_digest(path: Path) -> str:
    """The first 12 hex digits of the file's SHA-256, recorded with every result."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
