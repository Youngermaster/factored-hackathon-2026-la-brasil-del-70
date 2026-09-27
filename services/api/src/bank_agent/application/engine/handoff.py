"""``HandoffBuilder``: the structured handoff (``contracts/schemas/handoff.v1.json``) from verified state only.

It carries the request (a deterministic one-paragraph summary and the intent), the verified facts collected during
the conversation with their source references, the writes with their verification status, the policy basis, the
escalation reason, open questions from unresolved slots, the priority, and the SLA from ``ESC-<country>-2``
(``priority_handoff_sla_hours`` for distress, ``handoff_sla_hours`` otherwise) or ``CRD-ALL-3`` for card requests.
It never carries the transcript. Every handoff is validated against the JSON Schema generated from the model (the
same generation ``make contracts`` writes to the committed file) before it is stored.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from functools import cache
from typing import Any

import jsonschema

from bank_agent.application.engine.context import TurnContext
from bank_agent.domain.actions import ActionStatus
from bank_agent.domain.cards import CardRequest
from bank_agent.domain.complaint import Priority
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.errors import InvariantViolationError
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.handoff import (
    ActionTaken,
    EscalationReason,
    Handoff,
    HandoffAuth,
    HandoffRequest,
    Sentiment,
    VerificationStatus,
    VerifiedFact,
)
from bank_agent.domain.identifiers import CaseId, HandoffId, IdKind
from bank_agent.domain.locale import Language
from bank_agent.domain.trust import RiskTier
from bank_agent.domain.workflow import Intent

CARD_REQUEST_CODES = frozenset(
    {EscalationReasonCode.CARD_UNBLOCK_REQUESTED, EscalationReasonCode.CARD_REPLACEMENT_REQUESTED}
)
MAX_SUMMARY = 500


@dataclass(frozen=True)
class HandoffPlan:
    code: EscalationReasonCode
    detail: str
    intent: Intent
    open_questions: tuple[str, ...] = ()
    policy_basis: tuple[ClauseRef, ...] = ()
    card_request: CardRequest | None = None
    case_ref: CaseId | None = None
    summary_extra: tuple[str, ...] = field(default_factory=tuple)


@cache
def handoff_schema() -> dict[str, Any]:
    schema: dict[str, Any] = Handoff.model_json_schema(mode="serialization")
    return schema


def validate_handoff(handoff: Handoff) -> None:
    """Raise ``InvariantViolationError`` when the handoff does not fit the handoff JSON Schema."""
    validator = jsonschema.Draft202012Validator(handoff_schema())
    errors = sorted(validator.iter_errors(handoff.model_dump(mode="json")), key=lambda error: list(error.path))
    if errors:
        raise InvariantViolationError(f"handoff does not fit its schema at {list(errors[0].path)}")


def _hours(ctx: TurnContext, plan: HandoffPlan, urgent: bool) -> int:
    pack, language = ctx.services.policy.pack, Language.ES
    if plan.code in CARD_REQUEST_CODES:
        value = pack.get_clause("CRD-ALL-3", language).metadata.params["handoff_sla_hours"]
    else:
        params = pack.get_clause(f"ESC-{ctx.customer.country.value}-2", language).metadata.params
        value = params["priority_handoff_sla_hours" if urgent else "handoff_sla_hours"]
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvariantViolationError("handoff SLA hours must be an integer clause parameter")
    return value


def _summary(ctx: TurnContext, plan: HandoffPlan) -> str:
    parts = [
        f"Customer request ({plan.intent.value}) in workflow {ctx.workflow.value}, state {ctx.state}.",
        f"Escalated: {plan.code.value}.",
        f"Verified facts: {len(ctx.engine.facts)}; actions: {len(ctx.engine.executed)}.",
        *plan.summary_extra,
    ]
    return " ".join(parts)[:MAX_SUMMARY]


def _actions(ctx: TurnContext) -> tuple[ActionTaken, ...]:
    taken = []
    for item in ctx.engine.executed:
        if item.verified:
            status, verification = ActionStatus.EXECUTED, VerificationStatus.VERIFIED
        elif item.failed:
            status, verification = ActionStatus.FAILED, VerificationStatus.NOT_VERIFIED
        elif item.mismatch_code is not None:
            status, verification = ActionStatus.UNKNOWN, VerificationStatus.MISMATCH
        else:
            status, verification = ActionStatus.UNKNOWN, VerificationStatus.NOT_VERIFIED
        evidence = item.outcome_ref if item.verified else None
        taken.append(
            ActionTaken(
                action=item.action,
                target=item.target,
                confirmed=True,
                status=status,
                verification=verification,
                evidence=evidence,
            )
        )
    return tuple(taken[-10:])


class HandoffBuilder:
    def build(self, ctx: TurnContext, plan: HandoffPlan) -> Handoff:
        signals = ctx.escalation
        urgent = signals.distress_signal
        high = urgent or signals.legal_or_regulator_mention or ctx.trust.risk_tier is RiskTier.HIGH
        now = ctx.now
        sentiment = Sentiment.VERY_NEGATIVE if urgent else (Sentiment.NEGATIVE if high else Sentiment.UNKNOWN)
        handoff = Handoff(
            handoff_id=HandoffId(ctx.services.ids.new(IdKind.HANDOFF)),
            created_at=now,
            conversation_ref=ctx.conversation.conversation_id,
            case_ref=plan.case_ref,
            state_at_escalation=ctx.state,
            language=Language.PT if ctx.language is Language.PT else Language.ES,
            jurisdiction=ctx.customer.country,
            customer_ref=ctx.customer.customer_id,
            auth=HandoffAuth(level=ctx.snapshot.effective_auth_level, expires_at=ctx.session.absolute_expires_at),
            request=HandoffRequest(summary=_summary(ctx, plan), intent=plan.intent),
            verified_facts=tuple(VerifiedFact(fact=f.fact, source=f.source) for f in ctx.engine.facts),
            actions_taken=_actions(ctx),
            policy_basis=tuple(dict.fromkeys(plan.policy_basis)),
            escalation_reason=EscalationReason(code=plan.code, detail=plan.detail[:300]),
            open_questions=tuple(question[:300] for question in plan.open_questions[:10]),
            customer_sentiment=sentiment,
            priority=Priority.HIGH if high else Priority.MEDIUM,
            sla_due=now + timedelta(hours=_hours(ctx, plan, urgent)),
            workflow=ctx.definition.ref,
            card_request=plan.card_request,
        )
        validate_handoff(handoff)
        return handoff
