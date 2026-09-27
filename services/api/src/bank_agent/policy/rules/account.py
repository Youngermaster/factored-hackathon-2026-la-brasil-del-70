"""ACC and CRD rules: account and payment answers, card status, the protective block, and card requests."""

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.cards import CardAction
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.workflow import Intent
from bank_agent.policy.rules.context import CONVERSATION_RULES as RULES
from bank_agent.policy.rules.context import RuleContext
from bank_agent.policy.rules.registry import Verdict, fail, ok, typed_param


@RULES.rule(
    "ACC.product_owned_by_session_customer",
    version=1,
    reasons=("product_owned", "product_unknown", "product_not_owned"),
    missing_facts=("product",),
)
def product_owned(context: RuleContext) -> Verdict:
    account = context.facts.account
    owned = account.product_owned_by_session_customer if account is not None else None
    if owned is None:
        return fail(DecisionKind.CLARIFY, "product_unknown", missing=("product",))
    if not owned:
        return fail(DecisionKind.REFUSE, "product_not_owned")
    return ok("product_owned")


@RULES.rule(
    "ACC.statement_period_within_limit",
    version=1,
    params={"max_statement_days": int},
    reasons=(
        "statement_period_within_limit",
        "statement_period_unknown",
        "statement_period_invalid",
        "statement_period_too_long",
    ),
    missing_facts=("statement_period",),
)
def statement_period_within_limit(context: RuleContext) -> Verdict:
    limit = typed_param(context.params, "max_statement_days", int)
    account = context.facts.account
    days = account.statement_period_days if account is not None else None
    if days is None:
        return fail(DecisionKind.CLARIFY, "statement_period_unknown", missing=("statement_period",))
    if days < 1:
        return fail(DecisionKind.CLARIFY, "statement_period_invalid", period_days=days)
    if days > limit:
        return fail(DecisionKind.CLARIFY, "statement_period_too_long", period_days=days, max_statement_days=limit)
    return ok("statement_period_within_limit", period_days=days, max_statement_days=limit)


@RULES.rule(
    "ACC.as_of_disclosed", version=1, reasons=("as_of_disclosed", "as_of_missing"), missing_facts=("answer_as_of",)
)
def as_of_disclosed(context: RuleContext) -> Verdict:
    account = context.facts.account
    if account is None or account.answer_as_of is None:
        return fail(DecisionKind.ABSTAIN, "as_of_missing", missing=("answer_as_of",))
    return ok("as_of_disclosed")


def _blocking(context: RuleContext) -> bool:
    action = context.request.action
    return action is not None and action.action is ActionKind.BLOCK_CARD


@RULES.rule(
    "CRD.card_owned_by_session_customer",
    version=1,
    reasons=("card_owned", "card_unknown", "not_a_card", "card_not_owned"),
    missing_facts=("card",),
)
def card_owned(context: RuleContext) -> Verdict:
    card = context.facts.card
    if card is None:
        return fail(DecisionKind.CLARIFY, "card_unknown", missing=("card",))
    if not card.owned_by_session_customer:
        return fail(DecisionKind.REFUSE, "card_not_owned")
    if not card.is_card:
        return fail(DecisionKind.DENY, "not_a_card")
    return ok("card_owned")


@RULES.rule(
    "CRD.card_active",
    version=1,
    reasons=("no_block_requested", "card_active", "card_unknown", "card_already_blocked", "card_not_active"),
    missing_facts=("card",),
)
def card_active(context: RuleContext) -> Verdict:
    if not _blocking(context):
        return ok("no_block_requested")
    card = context.facts.card
    if card is None:
        return fail(DecisionKind.CLARIFY, "card_unknown", missing=("card",))
    if card.status is ProductStatus.BLOCKED:
        return fail(DecisionKind.ABSTAIN, "card_already_blocked")
    if card.status is not ProductStatus.ACTIVE:
        return fail(DecisionKind.DENY, "card_not_active", status=card.status.value)
    return ok("card_active")


@RULES.rule(
    "CRD.block_requires_step_up",
    version=1,
    params={"block_requires_step_up": bool},
    reasons=("no_block_requested", "step_up_not_required", "step_up_valid", "step_up_required"),
)
def block_requires_step_up(context: RuleContext) -> Verdict:
    if not _blocking(context):
        return ok("no_block_requested")
    if not typed_param(context.params, "block_requires_step_up", bool):
        return ok("step_up_not_required")
    session = context.request.session
    if session is not None and session.step_up_valid:
        return ok("step_up_valid")
    return fail(DecisionKind.REQUIRE_STEP_UP, "step_up_required")


def _card_request(context: RuleContext, action: CardAction, intent: Intent) -> bool:
    card = context.facts.card
    return context.facts.intent is intent or (card is not None and card.request is action)


@RULES.rule("CRD.unblock_requires_human", version=1, reasons=("no_unblock_request", "card_unblock_requested"))
def unblock_requires_human(context: RuleContext) -> Verdict:
    if _card_request(context, CardAction.UNBLOCK_REQUEST, Intent.CARD_UNBLOCK_REQUEST):
        return fail(DecisionKind.ESCALATE, "card_unblock_requested")
    return ok("no_unblock_request")


@RULES.rule(
    "CRD.replacement_requires_human", version=1, reasons=("no_replacement_request", "card_replacement_requested")
)
def replacement_requires_human(context: RuleContext) -> Verdict:
    if _card_request(context, CardAction.REPLACEMENT_REQUEST, Intent.CARD_REPLACEMENT_REQUEST):
        return fail(DecisionKind.ESCALATE, "card_replacement_requested")
    return ok("no_replacement_request")
