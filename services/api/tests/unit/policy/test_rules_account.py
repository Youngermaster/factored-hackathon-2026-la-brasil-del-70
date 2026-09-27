"""ACC and CRD rules: boundary values, and missing facts that fail safely."""

from datetime import datetime

import pytest

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.cards import CardAction
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.policy.facts import AccountFacts, CardFacts
from bank_agent.policy.rules import CONVERSATION_RULES, RuleContext
from bank_agent_policy import NOW, action, context, facts, request, snapshot


def run(rule_id: str, ctx: RuleContext) -> tuple[bool, str, DecisionKind | None, tuple[str, ...]]:
    result = CONVERSATION_RULES[rule_id].run(ctx, ())
    return result.passed, result.reason_code, result.effect, result.missing_facts


def account(**fields: object) -> RuleContext:
    facts_ = facts(intent=Intent.STATEMENT_REQUEST, account=AccountFacts.model_validate(fields))
    return context({"max_statement_days": 92}, request_=request(WorkflowId.ACCOUNT_INQUIRY, "X", facts_=facts_))


def card(*, action_kind: ActionKind | None = None, step_up: bool = False, **fields: object) -> RuleContext:
    values: dict[str, object] = {"owned_by_session_customer": True, "is_card": True, "status": ProductStatus.ACTIVE}
    values.update(fields)
    facts_ = facts(intent=Intent.CARD_BLOCK, card=CardFacts.model_validate(values))
    act = action(action_kind, "EXECUTE_BLOCK") if action_kind is not None else None
    req = request(
        WorkflowId.CARD_SUPPORT, "EXECUTE_BLOCK", facts_=facts_, action_=act, session=snapshot(step_up=step_up)
    )
    return context({"block_requires_step_up": True}, request_=req)


def test_product_ownership_needs_the_fact_and_refuses_another_customers_product() -> None:
    assert run("ACC.product_owned_by_session_customer", account())[1:] == (
        "product_unknown",
        DecisionKind.CLARIFY,
        ("product",),
    )
    assert run("ACC.product_owned_by_session_customer", account(product_owned_by_session_customer=False))[2] is (
        DecisionKind.REFUSE
    )
    assert run("ACC.product_owned_by_session_customer", account(product_owned_by_session_customer=True))[0]


@pytest.mark.parametrize(
    ("days", "reason"),
    [
        (1, "statement_period_within_limit"),
        (92, "statement_period_within_limit"),
        (93, "statement_period_too_long"),
        (0, "statement_period_invalid"),
        (None, "statement_period_unknown"),
    ],
)
def test_statement_period_boundaries(days: int | None, reason: str) -> None:
    assert run("ACC.statement_period_within_limit", account(statement_period_days=days))[1] == reason


def test_balances_are_never_answered_without_an_as_of_instant() -> None:
    assert run("ACC.as_of_disclosed", account())[2] is DecisionKind.ABSTAIN
    as_of: datetime = NOW
    assert run("ACC.as_of_disclosed", account(answer_as_of=as_of))[0]


def test_card_ownership() -> None:
    no_card = context(request_=request(WorkflowId.CARD_SUPPORT, "IDENTIFY_CARD", facts_=facts()))
    assert run("CRD.card_owned_by_session_customer", no_card)[1:] == ("card_unknown", DecisionKind.CLARIFY, ("card",))
    assert run("CRD.card_owned_by_session_customer", card(owned_by_session_customer=False))[2] is DecisionKind.REFUSE
    assert run("CRD.card_owned_by_session_customer", card(is_card=False))[1] == "not_a_card"
    assert run("CRD.card_owned_by_session_customer", card())[0]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ProductStatus.ACTIVE, (True, "card_active", None)),
        (ProductStatus.BLOCKED, (False, "card_already_blocked", DecisionKind.ABSTAIN)),
        (ProductStatus.CLOSED, (False, "card_not_active", DecisionKind.DENY)),
        (ProductStatus.SUSPENDED, (False, "card_not_active", DecisionKind.DENY)),
    ],
)
def test_only_an_active_card_can_be_blocked(status: ProductStatus, expected: tuple[object, ...]) -> None:
    assert run("CRD.card_active", card(action_kind=ActionKind.BLOCK_CARD, status=status))[:3] == expected


def test_card_status_does_not_matter_without_a_block_request() -> None:
    assert run("CRD.card_active", card(status=ProductStatus.BLOCKED))[1] == "no_block_requested"
    assert run("CRD.block_requires_step_up", card())[1] == "no_block_requested"


def test_a_block_requires_a_valid_step_up() -> None:
    assert run("CRD.block_requires_step_up", card(action_kind=ActionKind.BLOCK_CARD))[2] is DecisionKind.REQUIRE_STEP_UP
    assert run("CRD.block_requires_step_up", card(action_kind=ActionKind.BLOCK_CARD, step_up=True))[0]
    relaxed = card(action_kind=ActionKind.BLOCK_CARD)
    relaxed = RuleContext(relaxed.request, {"block_requires_step_up": False}, relaxed.state_auth, None)
    assert run("CRD.block_requires_step_up", relaxed)[1] == "step_up_not_required"


@pytest.mark.parametrize(
    ("rule_id", "request_kind", "reason"),
    [
        ("CRD.unblock_requires_human", CardAction.UNBLOCK_REQUEST, "card_unblock_requested"),
        ("CRD.replacement_requires_human", CardAction.REPLACEMENT_REQUEST, "card_replacement_requested"),
    ],
)
def test_unblock_and_replacement_always_go_to_a_human(rule_id: str, request_kind: CardAction, reason: str) -> None:
    assert run(rule_id, card(request=request_kind))[1:3] == (reason, DecisionKind.ESCALATE)
    assert run(rule_id, card())[0]


def test_an_unblock_intent_escalates_even_before_the_card_is_known() -> None:
    ctx = context(request_=request(WorkflowId.CARD_SUPPORT, "START", facts_=facts(intent=Intent.CARD_UNBLOCK_REQUEST)))
    assert run("CRD.unblock_requires_human", ctx)[2] is DecisionKind.ESCALATE
