"""Builders for grounding verifier tests over the in-memory fixture pack (every value is a fixture)."""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from bank_agent.application.grounding.draft import (
    FactKind,
    GroundingContext,
    RecordFact,
    ResponseDraft,
    VerifiedAction,
    Violation,
    ViolationKind,
)
from bank_agent.application.grounding.verifier import GroundingVerifier
from bank_agent.domain.actions import ActionKind, ActionResult, ActionStatus, Verification
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.policy import PolicyClause
from bank_agent.policy.pack import PolicyPack
from bank_agent_builders import T0, idempotency_key
from bank_agent_policy import fixture_pack

AS_OF = datetime(2026, 6, 17, 10, 30, tzinfo=UTC)


class NewerVersionRepository:
    """The fixture pack, except that ``DSP-MX-1`` is at version 2, so a citation of version 1 is stale."""

    def __init__(self, pack: PolicyPack) -> None:
        self._pack = pack

    def pack_version(self) -> str:
        return self._pack.pack_version()

    def get_clause(self, clause_id: str, language: Language, version: int | None = None) -> PolicyClause:
        clause = self._pack.get_clause(clause_id, language)
        if clause_id != "DSP-MX-1":
            return self._pack.get_clause(clause_id, language, version)
        newer = clause.model_copy(update={"metadata": clause.metadata.model_copy(update={"version": 2})})
        return clause if version == 1 else newer

    def __getattr__(self, name: str) -> Any:
        return getattr(self._pack, name)


def verifier() -> GroundingVerifier:
    return GroundingVerifier(fixture_pack())


def refs(*values: str) -> tuple[ClauseRef, ...]:
    return tuple(ClauseRef.parse(value) for value in values)


def draft(text: str, *citations: str) -> ResponseDraft:
    return ResponseDraft(text=text, citations=refs(*citations))


def context(**overrides: Any) -> GroundingContext:
    fields: dict[str, Any] = {"language": Language.ES, "jurisdiction": Country.MX, "currency": Currency.MXN}
    return GroundingContext.model_validate({**fields, **overrides})


def money_fact(kind: FactKind, amount: str, currency: Currency = Currency.MXN, fact_id: str = "f1") -> RecordFact:
    return RecordFact(fact_id=fact_id, kind=kind, money=Money.of(amount, currency))


def as_of(at: datetime = AS_OF) -> RecordFact:
    return RecordFact(fact_id="as_of", kind=FactKind.AS_OF, at=at)


def date_fact(day: date) -> RecordFact:
    return RecordFact(fact_id="d1", kind=FactKind.DATE, day=day)


def number_fact(kind: FactKind, value: int) -> RecordFact:
    return RecordFact(fact_id="n1", kind=kind, number=Decimal(value))


def verified_action(
    kind: ActionKind, *, verified: bool = True, status: ActionStatus = ActionStatus.EXECUTED
) -> VerifiedAction:
    result = ActionResult.model_validate(
        {
            "action": kind,
            "idempotency_key": idempotency_key(),
            "status": status,
            "error_code": None if status is ActionStatus.EXECUTED else "tool_timeout",
            "attempts": 1,
            "completed_at": T0,
        }
    )
    verification = Verification.model_validate(
        {
            "verified": verified,
            "check": "read_back",
            "evidence": "products:PRD-A-0001" if verified else None,
            "mismatch_code": None if verified else "status_unchanged",
            "checked_at": T0,
        }
    )
    return VerifiedAction(result=result, verification=verification)


def kinds(violations: Sequence[Violation]) -> list[ViolationKind]:
    return [violation.kind for violation in violations]
