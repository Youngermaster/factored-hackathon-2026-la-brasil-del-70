"""What a handler asks the engine to say: a template id with typed parameters, clauses to explain, the grounding
facts behind every figure, and the structured parts of ``AssistantResponse``.

Handlers never write customer text themselves. Parameters are typed so the renderer formats them per locale, and
record text (a merchant name) is wrapped in ``RecordText`` so it is quoted as data: the grounding verifier sees a
neutral placeholder in its place, and no figure inside it can count as a claim.
"""

from dataclasses import dataclass, field
from datetime import date

from bank_agent.application.grounding.draft import RecordFact
from bank_agent.domain.accounts import BalanceView, PaymentStatusView, StatementSummary
from bank_agent.domain.cards import CardStatusView
from bank_agent.domain.conversation import (
    ActionStatusView,
    CardActionConfirmation,
    Clarification,
    ConfirmationCard,
    CreditIntakeConfirmation,
    EscalationNotice,
    NoticeCode,
)
from bank_agent.domain.credit import CreditProduct, CreditProfile
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.eligibility import EligibilityAssessment, EligibilityView, RiskEstimate
from bank_agent.domain.money import Money


@dataclass(frozen=True)
class RecordText:
    """Untrusted record text quoted in a reply (merchant names). Rendered as plain text, never verified as a claim."""

    text: str


@dataclass(frozen=True)
class Masked:
    """The last four characters of a card or account, rendered as ``**** 1234``."""

    last4: str


@dataclass(frozen=True)
class Choices:
    """A numbered list of options rendered one per line (each line is itself a template with parameters)."""

    template: str
    items: tuple[dict[str, "Param"], ...]


Param = Money | date | int | str | RecordText | Masked | Choices


@dataclass(frozen=True)
class CreditEvidence:
    """What a credit reply may rely on, for the grounding verifier and for optional phrasing.

    ``assessment`` and ``product`` are evidence (an outcome claim must match the assessment; catalog figures must
    match the entry). ``profile``, ``estimate``, and ``declared_income`` reach only the verifier, as figures that
    must never appear. Phrasing receives only ``outcome``, ``reasons``, and ``disclaimer``: never the profile, the
    estimate, or any of their values.
    """

    assessment: EligibilityAssessment | None = None
    product: CreditProduct | None = None
    profile: CreditProfile | None = None
    estimate: RiskEstimate | None = None
    declared_income: Money | None = None
    outcome: str | None = None
    reasons: tuple[str, ...] = ()
    disclaimer: str | None = None


@dataclass(frozen=True)
class Reply:
    template: str
    params: dict[str, Param] = field(default_factory=dict)
    explain: tuple[ClauseRef, ...] = ()
    """Clauses whose customer-facing text is appended (rendered by the policy renderer) and cited."""
    facts: tuple[RecordFact, ...] = ()
    clarification: Clarification | None = None
    confirmation: ConfirmationCard | None = None
    card_action_confirmation: CardActionConfirmation | None = None
    credit_intake_confirmation: CreditIntakeConfirmation | None = None
    credit_products: tuple[CreditProduct, ...] = ()
    eligibility: EligibilityView | None = None
    """The customer-facing view only: outcome, reasons, uncertainty, review path, disclaimer; never the estimate."""
    action_statuses: tuple[ActionStatusView, ...] = ()
    escalation: EscalationNotice | None = None
    step_up_required: bool = False
    notices: tuple[NoticeCode, ...] = ()
    card_status: tuple[CardStatusView, ...] = ()
    balances: tuple[BalanceView, ...] = ()
    """Balances with their as-of instant, as structured parts next to the rendered text (phase 11)."""
    payment_statuses: tuple[PaymentStatusView, ...] = ()
    statement: StatementSummary | None = None
    suffix: tuple[tuple[str, dict[str, "Param"]], ...] = ()
    """Further templates appended after the main one, each with its own parameters."""
    prefix: str | None = None
    """A template rendered before the main one (``common.resume`` after re-authentication)."""
    bilingual: bool = False
    """Render the template in Spanish and Portuguese together (the language question)."""
    cite: tuple[ClauseRef, ...] = ()
    """Clauses whose text is already part of a parameter (the rendered eligibility explanation): cited and used as
    evidence, but not appended again."""
    credit: CreditEvidence | None = None
