"""What the policy evaluator receives. Every fact is passed in; the kernel performs no I/O and reads no clock.

Two kinds of facts:

- **Record facts** (a transaction, a card, a product, a credit product) are optional. A rule whose record fact
  is missing fails safely (usually ``clarify``) and names the missing fact; it never raises.
- **Detector signals** (a human request, a legal mention, distress, a third-party request) default to "not
  detected". The workflow engine sets them from its detectors; the kernel never parses customer text.

``PolicyFacts.data_as_of`` is the reference date of every time window (the dispute window, the complaint
lookback). It is the as-of date of the records, supplied by the composition root, never the wall clock: the
organizer data ends at the 2026-06-17 snapshot.
"""

from datetime import date, datetime

from pydantic import Field, NonNegativeInt

from bank_agent.domain.actions import ActionRequest
from bank_agent.domain.base import DomainModel
from bank_agent.domain.cards import CardAction
from bank_agent.domain.credit import CreditProduct
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.eligibility import EligibilityOutcome
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Money
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.session import SessionSnapshot
from bank_agent.domain.transaction import TransactionStatus
from bank_agent.domain.trust import RiskTier, TrustState
from bank_agent.domain.workflow import Intent, StateName, WorkflowId


class PrivacySignals(DomainModel):
    other_customer_reference: bool = False
    """The request names a record or person that the session does not own (a cross-customer probe)."""
    third_party_request: bool = False
    """The customer asks on behalf of someone else, or asks for someone else's information."""


class EscalationSignals(DomainModel):
    human_requested: bool = False
    legal_or_regulator_mention: bool = False
    distress_signal: bool = False
    clarification_attempts: NonNegativeInt = 0
    tool_failures_after_retries: NonNegativeInt = 0
    verification_mismatch: bool = False
    prior_complaints_in_lookback: NonNegativeInt = 0
    """The customer's complaints within the ``ESC-ALL-1`` lookback before ``data_as_of``, counted by the caller."""
    eligibility_contested: bool = False


class AccountFacts(DomainModel):
    product_owned_by_session_customer: bool | None = None
    statement_period_days: int | None = None
    answer_as_of: datetime | None = None
    """The as-of instant the answer states; balances and statements are never given without it."""


class CardFacts(DomainModel):
    owned_by_session_customer: bool
    is_card: bool
    status: ProductStatus
    request: CardAction | None = None


class TransactionFacts(DomainModel):
    owned_by_session_customer: bool
    status: TransactionStatus
    occurred_on: date
    """The customer-local date of the transaction."""
    amount: Money
    has_open_dispute: bool = False


class DisputeFacts(DomainModel):
    transaction: TransactionFacts | None = None
    reason: DisputeReason | None = None
    disputed_amount: Money | None = None


class CreditFacts(DomainModel):
    requested_product_code: str | None = None
    product: CreditProduct | None = None
    """The catalog entry for the requested code, or ``None`` when the catalog has no such product."""
    disclaimer_included: bool = False
    eligibility_outcome: EligibilityOutcome | None = None


class PolicyFacts(DomainModel):
    jurisdiction: Country
    """From the verified customer profile, never from user text."""
    data_as_of: date
    intent: Intent | None = None
    privacy: PrivacySignals = Field(default_factory=PrivacySignals)
    escalation: EscalationSignals = Field(default_factory=EscalationSignals)
    account: AccountFacts | None = None
    card: CardFacts | None = None
    dispute: DisputeFacts | None = None
    credit: CreditFacts | None = None


class EvaluationRequest(DomainModel):
    """One evaluation: where the conversation is, what it wants to do, who is asking, and the facts."""

    workflow: WorkflowId
    state: StateName
    action: ActionRequest | None = None
    session: SessionSnapshot | None = None
    trust: TrustState | None = None
    facts: PolicyFacts

    @property
    def risk_tier(self) -> RiskTier:
        return self.trust.risk_tier if self.trust is not None else RiskTier.LOW
