"""The handoff reason picked for an escalate decision never names a section the handoff lacks (QA finding CRD-01).

A replacement or unblock request keeps its CRD rule decisive in every IDENTIFY_CARD evaluation. When the which-card
budget runs out, the escalation has no card request yet, so the reason must come from the next decisive rule
instead of producing a handoff that fails validation (an HTTP 500 in production).
"""

from bank_agent.application.engine.shared import escalation_code
from bank_agent.domain.cards import CardAction, CardRequest
from bank_agent.domain.decision import Decision, DecisionKind, RuleResult
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.identifiers import SourceRef


def _failing(rule_id: str) -> RuleResult:
    return RuleResult(rule_id=rule_id, rule_version=1, passed=False, effect=DecisionKind.ESCALATE, reason_code="failed")


def _decision(*rule_ids: str) -> Decision:
    return Decision.build(
        state="IDENTIFY_CARD",
        kind=DecisionKind.ESCALATE,
        rule_results=tuple(_failing(rule_id) for rule_id in rule_ids),
        policy_pack_version="test",
        decisive_rule_ids=rule_ids,
    )


def _request(action: CardAction) -> CardRequest:
    return CardRequest(action=action, product_ref=SourceRef.model_validate("products:P1"))


def test_exhausted_clarification_during_replacement_request_without_card_names_clarification_exhausted() -> None:
    decision = _decision("CRD.replacement_requires_human", "ESC.clarification_exhausted")
    assert escalation_code(decision) is EscalationReasonCode.CLARIFICATION_EXHAUSTED


def test_exhausted_clarification_during_unblock_request_without_card_names_clarification_exhausted() -> None:
    decision = _decision("CRD.unblock_requires_human", "ESC.clarification_exhausted")
    assert escalation_code(decision) is EscalationReasonCode.CLARIFICATION_EXHAUSTED


def test_replacement_request_with_its_card_request_keeps_the_card_reason() -> None:
    decision = _decision("CRD.replacement_requires_human", "ESC.clarification_exhausted")
    code = escalation_code(decision, card_request=_request(CardAction.REPLACEMENT_REQUEST))
    assert code is EscalationReasonCode.CARD_REPLACEMENT_REQUESTED


def test_card_request_for_another_action_does_not_select_the_card_reason() -> None:
    decision = _decision("CRD.replacement_requires_human", "ESC.tool_failure_exhausted")
    code = escalation_code(decision, card_request=_request(CardAction.UNBLOCK_REQUEST))
    assert code is EscalationReasonCode.TOOL_FAILURE


def test_card_reason_alone_without_card_request_falls_back_to_other() -> None:
    assert escalation_code(_decision("CRD.replacement_requires_human")) is EscalationReasonCode.OTHER


def test_credit_review_reason_without_credit_review_uses_the_next_decisive_rule() -> None:
    decision = _decision("ESC.credit_review_required", "ESC.clarification_exhausted")
    assert escalation_code(decision) is EscalationReasonCode.CLARIFICATION_EXHAUSTED


def _amount_decision(reason_code: str) -> Decision:
    result = RuleResult(
        rule_id="DSP.amount_within_auto_limit",
        rule_version=2,
        passed=False,
        effect=DecisionKind.ESCALATE,
        reason_code=reason_code,
    )
    return Decision.build(
        state="CONFIRM_DISPUTE",
        kind=DecisionKind.ESCALATE,
        rule_results=(result,),
        policy_pack_version="test",
        decisive_rule_ids=("DSP.amount_within_auto_limit",),
    )


def test_amount_in_a_currency_without_a_pack_rate_is_handed_off_as_needing_a_person_not_above_the_limit() -> None:
    code = escalation_code(_amount_decision("amount_not_comparable"))
    assert code is EscalationReasonCode.UNSUPPORTED_NEEDS_HUMAN


def test_amount_above_the_limit_keeps_the_amount_reason() -> None:
    code = escalation_code(_amount_decision("amount_above_auto_limit"))
    assert code is EscalationReasonCode.AMOUNT_ABOVE_AUTO_LIMIT
