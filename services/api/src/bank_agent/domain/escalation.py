"""Why a conversation is handed to a human agent.

The codes live in their own module so that the card, credit, and handoff modules can all use them without an
import cycle; ``bank_agent.domain.handoff`` re-exports ``EscalationReasonCode`` unchanged.
"""

from enum import StrEnum


class EscalationReasonCode(StrEnum):
    AMOUNT_ABOVE_AUTO_LIMIT = "amount_above_auto_limit"
    REPEAT_COMPLAINER = "repeat_complainer"
    LEGAL_OR_REGULATOR_MENTION = "legal_or_regulator_mention"
    DISTRESS_SIGNAL = "distress_signal"
    HUMAN_REQUESTED = "human_requested"
    CLARIFICATION_EXHAUSTED = "clarification_exhausted"
    TOOL_FAILURE = "tool_failure"
    VERIFICATION_MISMATCH = "verification_mismatch"
    RISK_TIER_HIGH = "risk_tier_high"
    SLA_BREACHED = "sla_breached"
    UNSUPPORTED_NEEDS_HUMAN = "unsupported_needs_human"
    OTHER = "other"
    CARD_UNBLOCK_REQUESTED = "card_unblock_requested"
    """Unblocking after a protective block needs identity and fraud checks the prototype cannot verify."""
    CARD_REPLACEMENT_REQUESTED = "card_replacement_requested"
    """Issuing a card needs identity and fraud checks the prototype cannot verify."""
    CREDIT_REVIEW_REQUIRED = "credit_review_required"
    """A borderline or missing-data eligibility result needs a human reviewer."""
    ELIGIBILITY_CONTESTED = "eligibility_contested"
    """The customer contests an indicative eligibility result."""
