"""What the language model may return, and what it may never receive.

Each prompt with a structured output names one model from ``OUTPUT_MODELS`` in its front matter. The gateway
derives the JSON Schema from the model and validates the reply against it. Extraction fields have no defaults:
the model must write ``null`` explicitly when the customer did not say something, so a missing key is an
invalid output rather than a silent guess. The models describe understanding only (what the customer said
and wants); they carry no workflow decision, no eligibility judgement, and no action.

``FORBIDDEN_PROMPT_VARIABLE_NAMES`` and ``FORBIDDEN_PROMPT_VARIABLE_TOKENS`` list names that no prompt may
declare as an input, because they would carry a risk estimate, a credit profile fact, or an internal flag to a
provider (CLAUDE.md section 1, credit rules). The prompt registry refuses to load a prompt that declares one.
"""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from bank_agent.domain.base import DomainModel, Pii, SummaryText, UntrustedText, internal_fields
from bank_agent.domain.cards import CardAction, CardBlockReason
from bank_agent.domain.credit import CreditProductType, CreditProfile
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.eligibility import CreditRiskFeatures, RiskEstimate
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.handoff import Handoff
from bank_agent.domain.intelligence import Probability, TransactionDescriptor
from bank_agent.domain.money import Amount, Currency
from bank_agent.domain.product import ProductType
from bank_agent.domain.transaction import Transaction, TransactionChannel
from bank_agent.domain.workflow import Intent

ExtractedText = Annotated[UntrustedText, StringConstraints(min_length=1, max_length=150)]
DigitsLast4 = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$")]
NonNegativeAmount = Annotated[Amount, Field(ge=0)]
CARD_PRODUCT_TYPES = frozenset({ProductType.CREDIT_CARD, ProductType.DEBIT_CARD})


class IntentCandidate(DomainModel):
    intent: Intent
    confidence: Probability


class ExtractedTransaction(DomainModel):
    """A transaction as the customer described it. Dates stay as the customer's words; the resolver
    interprets them deterministically."""

    amount: NonNegativeAmount | None
    currency_hint: Currency | None
    merchant_text: ExtractedText | None
    date_expression: Annotated[UntrustedText, StringConstraints(min_length=1, max_length=100)] | None
    channel_hint: TransactionChannel | None
    card_last4_hint: DigitsLast4 | None

    def to_descriptor(self) -> TransactionDescriptor:
        return TransactionDescriptor(
            amount=self.amount,
            currency_hint=self.currency_hint,
            merchant_text=self.merchant_text,
            date_expression=self.date_expression,
            channel_hint=self.channel_hint,
            card_last4_hint=self.card_last4_hint,
        )


class DisputeSlotExtraction(DomainModel):
    """``extract_dispute_slots``: intent candidates, the transaction, and the dispute reason candidates."""

    intent_candidates: Annotated[tuple[IntentCandidate, ...], Field(max_length=4)]
    transaction: ExtractedTransaction | None
    reason_candidates: Annotated[tuple[DisputeReason, ...], Field(max_length=3)]


class ProductHint(DomainModel):
    product_type: ProductType | None
    last4: DigitsLast4 | None


class PaymentDescriptor(DomainModel):
    amount: NonNegativeAmount | None
    currency_hint: Currency | None
    date_expression: Annotated[UntrustedText, StringConstraints(min_length=1, max_length=100)] | None
    payee_text: ExtractedText | None


class AccountInquirySlotExtraction(DomainModel):
    """``extract_account_inquiry_slots``: which product, which statement period, which payment."""

    product_hint: ProductHint | None
    statement_period_expression: Annotated[UntrustedText, StringConstraints(min_length=1, max_length=100)] | None
    payment: PaymentDescriptor | None


class CardHint(DomainModel):
    card_type: ProductType | None
    last4: DigitsLast4 | None

    @model_validator(mode="after")
    def _only_cards(self) -> Self:
        if self.card_type is not None and self.card_type not in CARD_PRODUCT_TYPES:
            raise ValueError("a card hint names a credit or debit card")
        return self


class CardSupportSlotExtraction(DomainModel):
    """``extract_card_support_slots``: which card, which card action, and why a block is wanted."""

    card_hint: CardHint | None
    requested_action: CardAction | None
    block_reason_candidates: Annotated[tuple[CardBlockReason, ...], Field(max_length=4)]


class CreditSlotExtraction(DomainModel):
    """``extract_credit_slots``: only what the customer said. The model never estimates, completes, or judges
    eligibility; a declared income is the customer's own statement and never reaches another prompt."""

    product_of_interest: CreditProductType | None
    requested_amount: NonNegativeAmount | None
    currency_hint: Currency | None
    requested_term_months: Annotated[int, Field(ge=1, le=480)] | None
    purpose: ExtractedText | None
    declared_monthly_income: Annotated[NonNegativeAmount, Pii("financial")] | None


class FallbackIntentLabel(StrEnum):
    """The label set of ``classify_intent_fallback``: every ``Intent`` plus ``out_of_scope``. A test keeps the
    two in step. The labels are intents, never workflow decisions."""

    DISPUTE_NEW = "dispute_new"
    DISPUTE_STATUS = "dispute_status"
    CARD_BLOCK = "card_block"
    INFORMATIONAL = "informational"
    UNSUPPORTED = "unsupported"
    HUMAN_REQUEST = "human_request"
    GREETING_OR_OTHER = "greeting_or_other"
    BALANCE_INQUIRY = "balance_inquiry"
    PAYMENT_STATUS = "payment_status"
    STATEMENT_REQUEST = "statement_request"
    CARD_STATUS = "card_status"
    CARD_UNBLOCK_REQUEST = "card_unblock_request"
    CARD_REPLACEMENT_REQUEST = "card_replacement_request"
    CREDIT_PRODUCT_INFO = "credit_product_info"
    CREDIT_ELIGIBILITY = "credit_eligibility"
    CREDIT_APPLICATION = "credit_application"
    CREDIT_APPLICATION_STATUS = "credit_application_status"
    OUT_OF_SCOPE = "out_of_scope"

    @property
    def intent(self) -> Intent | None:
        """The matching ``Intent``, or ``None`` for ``out_of_scope``."""
        return None if self is FallbackIntentLabel.OUT_OF_SCOPE else Intent(self.value)


class IntentLabelScore(DomainModel):
    label: FallbackIntentLabel
    confidence: Probability


class IntentClassification(DomainModel):
    """``classify_intent_fallback``: ranked labels, best first."""

    candidates: Annotated[tuple[IntentLabelScore, ...], Field(min_length=1, max_length=5)]

    @model_validator(mode="after")
    def _distinct(self) -> Self:
        labels = [candidate.label for candidate in self.candidates]
        if len(labels) != len(set(labels)):
            raise ValueError("a label can appear only once")
        return self


class EscalationSignals(DomainModel):
    """``detect_escalation_signals``: each signal is stated explicitly, true or false."""

    legal_or_regulator_mention: bool
    distress: bool
    human_requested: bool
    third_party_admission: bool

    @property
    def any(self) -> bool:
        return self.legal_or_regulator_mention or self.distress or self.human_requested or self.third_party_admission


FactId = Annotated[str, StringConstraints(pattern=r"^F[0-9]{1,2}$")]


class HandoffSummaryDraft(DomainModel):
    """``summarize_for_handoff``: one paragraph built only from the numbered verified facts it cites. The
    grounding verifier re-checks every cited id against the facts that were passed in."""

    summary: SummaryText
    cited_fact_ids: Annotated[tuple[FactId, ...], Field(min_length=1, max_length=20)]


OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    model.__name__: model
    for model in (
        DisputeSlotExtraction,
        AccountInquirySlotExtraction,
        CardSupportSlotExtraction,
        CreditSlotExtraction,
        IntentClassification,
        EscalationSignals,
        HandoffSummaryDraft,
    )
}
"""Every structured output a prompt may name, by class name."""


def _leaf_names(paths: frozenset[str]) -> set[str]:
    return {path.rsplit(".", 1)[-1] for path in paths}


FORBIDDEN_PROMPT_VARIABLE_NAMES: frozenset[str] = frozenset(
    _leaf_names(internal_fields(CreditProfile))
    | _leaf_names(internal_fields(RiskEstimate))
    | _leaf_names(internal_fields(Transaction))
    | _leaf_names(internal_fields(ExecutionRecord))
    | _leaf_names(internal_fields(Handoff))
    | (set(CreditRiskFeatures.model_fields) - {"jurisdiction", "product_type"})
    | {"days_past_due", "risk_estimate", "credit_profile", "credit_review"}
)
"""Exact variable names that would carry internal data: every internal-only field of the credit profile, the
risk estimate, transactions, execution records, and handoffs, and every risk feature."""

FORBIDDEN_PROMPT_VARIABLE_TOKENS: frozenset[str] = frozenset(
    {"risk", "fraud", "score", "probability", "income", "utilization", "internal", "flag", "flags", "band"}
)
"""Words that may not appear as an underscore-separated part of any prompt variable name."""


def forbidden_variable_reason(name: str) -> str | None:
    """Explain why ``name`` may not be a prompt variable, or return ``None`` when it may."""
    if name in FORBIDDEN_PROMPT_VARIABLE_NAMES:
        return f"{name} is an internal field"
    if "days_past_due" in name:
        return f"{name} carries days past due"
    tokens = set(name.split("_")) & FORBIDDEN_PROMPT_VARIABLE_TOKENS
    if tokens:
        return f"{name} contains the internal word {sorted(tokens)[0]}"
    return None
