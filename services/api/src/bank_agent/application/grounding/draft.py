"""What the grounding verifier checks: a response draft, the evidence passed in with it, and typed violations."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from bank_agent.domain.actions import ActionKind, ActionResult, ActionStatus, Verification
from bank_agent.domain.base import DomainModel
from bank_agent.domain.credit import CreditProduct, CreditProfile
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.eligibility import EligibilityAssessment, RiskEstimate
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import WorkflowId


class FactKind(StrEnum):
    BALANCE = "balance"
    AVAILABLE_CREDIT = "available_credit"
    CREDIT_LIMIT = "credit_limit"
    STATEMENT_TOTAL = "statement_total"
    AMOUNT = "amount"
    AS_OF = "as_of"
    DATE = "date"
    COUNT = "count"
    DAYS = "days"
    REFERENCE = "reference"


MONEY_FACTS = frozenset(
    {FactKind.BALANCE, FactKind.AVAILABLE_CREDIT, FactKind.CREDIT_LIMIT, FactKind.STATEMENT_TOTAL, FactKind.AMOUNT}
)
BALANCE_FACTS = frozenset({FactKind.BALANCE, FactKind.AVAILABLE_CREDIT, FactKind.CREDIT_LIMIT})
_FACT_FIELDS: dict[FactKind, frozenset[str]] = {
    FactKind.AS_OF: frozenset({"at", "day"}),
    FactKind.DATE: frozenset({"day"}),
    FactKind.COUNT: frozenset({"number"}),
    FactKind.DAYS: frozenset({"number"}),
    FactKind.REFERENCE: frozenset({"reference"}),
}


class RecordFact(DomainModel):
    """One verified fact from the records, passed in with the draft. Exactly one value field is set."""

    fact_id: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    kind: FactKind
    money: Money | None = None
    day: date | None = None
    at: datetime | None = None
    """An as-of instant, already in the customer's time zone, so a written time can be compared."""
    number: Decimal | None = None
    reference: Annotated[str, StringConstraints(pattern=r"^\d{2,6}$")] | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        fields = {
            "money": self.money,
            "day": self.day,
            "at": self.at,
            "number": self.number,
            "reference": self.reference,
        }
        present = [name for name, value in fields.items() if value is not None]
        allowed = _FACT_FIELDS.get(self.kind, frozenset({"money"}))
        if len(present) != 1 or present[0] not in allowed:
            raise ValueError(f"a {self.kind} fact carries exactly one value, in {' or '.join(sorted(allowed))}")
        return self

    @property
    def as_of_date(self) -> date | None:
        return self.at.date() if self.at is not None else self.day


class VerifiedAction(DomainModel):
    """An action result with its read-back verification; only an executed and verified action may be claimed."""

    result: ActionResult
    verification: Verification | None = None

    @property
    def kind(self) -> ActionKind:
        return self.result.action

    @property
    def verified(self) -> bool:
        return (
            self.result.status is ActionStatus.EXECUTED and self.verification is not None and self.verification.verified
        )


class GroundingContext(DomainModel):
    """The evidence a draft may rely on. The jurisdiction comes from the verified customer record."""

    workflow: WorkflowId | None = None
    language: Language
    jurisdiction: Country
    currency: Currency | None = None
    """The account currency; a bare ``$`` or ``pesos`` resolves to it, and any other currency conflicts."""
    facts: tuple[RecordFact, ...] = ()
    bound_clauses: tuple[ClauseRef, ...] = ()
    """Clauses bound to the state, whose parameters may be stated even when not cited."""
    actions: tuple[VerifiedAction, ...] = ()
    eligibility: EligibilityAssessment | None = None
    catalog_product: CreditProduct | None = None
    credit_profile: CreditProfile | None = None
    risk_estimate: RiskEstimate | None = None
    declared_income: Money | None = None

    @property
    def is_credit(self) -> bool:
        return self.workflow is WorkflowId.CREDIT or any(
            value is not None
            for value in (self.eligibility, self.catalog_product, self.credit_profile, self.risk_estimate)
        )


class ResponseDraft(DomainModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=20000)]
    citations: Annotated[tuple[ClauseRef, ...], Field(max_length=30)] = ()


class ViolationKind(StrEnum):
    UNKNOWN_CLAUSE = "unknown_clause"
    STALE_CLAUSE_VERSION = "stale_clause_version"
    CLAUSE_OUTSIDE_JURISDICTION = "clause_outside_jurisdiction"
    UNSUPPORTED_AMOUNT = "unsupported_amount"
    UNSUPPORTED_DURATION = "unsupported_duration"
    UNSUPPORTED_DATE = "unsupported_date"
    UNSUPPORTED_NUMBER = "unsupported_number"
    UNSUPPORTED_REFERENCE = "unsupported_reference"
    CURRENCY_CONFLICT = "currency_conflict"
    CURRENCY_UNRESOLVED = "currency_unresolved"
    UNVERIFIED_ACTION_CLAIM = "unverified_action_claim"
    UNSUPPORTED_ACTION_CLAIM = "unsupported_action_claim"
    BALANCE_MISMATCH = "balance_mismatch"
    BALANCE_WITHOUT_AS_OF = "balance_without_as_of"
    STATEMENT_TOTAL_MISMATCH = "statement_total_mismatch"
    RATE_NOT_IN_CATALOG = "rate_not_in_catalog"
    CATALOG_FIGURE_MISMATCH = "catalog_figure_mismatch"
    CATALOG_JURISDICTION_MISMATCH = "catalog_jurisdiction_mismatch"
    ELIGIBILITY_WITHOUT_ASSESSMENT = "eligibility_without_assessment"
    ELIGIBILITY_OUTCOME_MISMATCH = "eligibility_outcome_mismatch"
    APPROVAL_WORDING = "approval_wording"
    INTERNAL_FIGURE_DISCLOSED = "internal_figure_disclosed"


class Violation(DomainModel):
    """One failed check. ``detail`` names the check, never a customer value; ``span`` locates it in the draft."""

    kind: ViolationKind
    detail: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    span: tuple[int, int] | None = None
    clause_id: str | None = None
    action: ActionKind | None = None
