"""CONFIRM_BLOCK, EXECUTE, and VERIFY for card support: the same step-up, confirmation, idempotent execution, and
read-back as the dispute path, with the block reason recorded. After a protective block offered before a
replacement request, the handoff follows whether the block was accepted or declined."""

from dataclasses import replace

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import evaluate, explanation
from bank_agent.application.engine.definition import RESOLVED
from bank_agent.application.engine.idempotency import derive_key
from bank_agent.application.engine.reply import Masked, Param, Reply
from bank_agent.application.engine.shared import (
    abstain,
    blocking_step,
    clause_ref,
    escalate_decision,
    spend_clarification,
)
from bank_agent.application.engine.templates.labels import CARD_TYPES
from bank_agent.application.understanding.answers import YesNo, parse_yes_no
from bank_agent.application.workflows.card_support.data import CardData, load, save
from bank_agent.application.workflows.card_support.select import card_ref
from bank_agent.application.workflows.shared.writes import PlannedWrite, ReadBack, execute_writes, verify_writes
from bank_agent.domain.actions import ActionKind, ActionRequest, BlockCardArguments, ToolName
from bank_agent.domain.cards import CardAction, CardBlockReason, CardRequest
from bank_agent.domain.conversation import ActionDisplayStatus, ActionStatusView, CardActionConfirmation
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.identifiers import SourceRef, SourceTable
from bank_agent.domain.locale import Language
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.workflow import Outcome
from bank_agent.policy.facts import CardFacts

CONFIRM_BLOCK = "CONFIRM_BLOCK"
EXECUTE = "EXECUTE"
VERIFY = "VERIFY"


def _params(ctx: TurnContext, data: CardData) -> dict[str, Param]:
    language = Language.ES if ctx.language is Language.EN else ctx.language
    kind = CARD_TYPES[data.card_type][language] if data.card_type is not None else ""
    return {"type": kind, "card": Masked(data.last4 or "----")}


def _facts(data: CardData) -> CardFacts:
    return CardFacts(owned_by_session_customer=True, is_card=True, status=data.status or ProductStatus.ACTIVE)


def block_request(ctx: TurnContext, data: CardData, *, confirmed: bool, state: str) -> ActionRequest | None:
    target = card_ref(data)
    if target is None or data.product_id is None:
        return None
    return ActionRequest(
        action=ActionKind.BLOCK_CARD,
        target=target,
        arguments=BlockCardArguments(
            product_id=data.product_id, reason=data.block_reason or CardBlockReason.PRECAUTION
        ),
        idempotency_key=derive_key(ctx.conversation.conversation_id, target, ActionKind.BLOCK_CARD),
        requested_in_state=state,
        confirmed_at=ctx.now if confirmed else None,
    )


def _handoff(ctx: TurnContext, data: CardData) -> Step:
    target = card_ref(data)
    facts = CardFacts(
        owned_by_session_customer=True, is_card=True, status=data.status or ProductStatus.ACTIVE, request=data.action
    )
    decision = evaluate(ctx, policy_state="CARD_REQUEST_HANDOFF", card=facts)
    request = CardRequest(action=data.action, product_ref=target) if data.action and target else None
    return escalate_decision(ctx, decision, card_request=request)


async def confirm_block(ctx: TurnContext) -> Step:
    data = load(ctx)
    if data.confirm_shown and not ctx.reprompt:
        answer = parse_yes_no(ctx.text)
        if answer is YesNo.YES:
            return Step(EXECUTE)
        if answer is YesNo.NO:
            save(ctx, data.evolve(confirm_shown=False))
            if data.block_first and data.action is CardAction.REPLACEMENT_REQUEST:
                return _handoff(ctx, data)
            return Step(RESOLVED, Reply(template="common.nothing_recorded"), Outcome.RESOLVED)
        stop = spend_clarification(ctx)
        if stop is not None:
            return stop
    request = block_request(ctx, data, confirmed=False, state=CONFIRM_BLOCK)
    decision = evaluate(ctx, action=request, card=_facts(data))
    stop = blocking_step(ctx, decision, state=CONFIRM_BLOCK, step_up_ok=True)
    if stop is not None:
        return stop
    if decision.kind is DecisionKind.ABSTAIN:
        return abstain(ctx, "card.already_blocked", explanation(decision), _params(ctx, data))
    if decision.kind is DecisionKind.DENY:
        return abstain(ctx, "card.not_blockable", explanation(decision), _params(ctx, data))
    save(ctx, data.evolve(confirm_shown=True))
    confirmation = CardActionConfirmation(
        action=CardAction.BLOCK,
        card_last4=data.last4 or "0000",
        reason=data.block_reason,
        planned_actions=(ActionKind.BLOCK_CARD,),
    )
    template = "card.offer_block_first" if data.block_first else "card.confirm_block"
    reply = Reply(
        template=template,
        params=_params(ctx, data),
        explain=(clause_ref(ctx, "CRD-ALL-2"),),
        card_action_confirmation=confirmation,
        prefix="common.confirm_again" if data.confirm_shown and not ctx.reprompt else None,
    )
    return Step(CONFIRM_BLOCK, reply, Outcome.IN_PROGRESS)


async def execute(ctx: TurnContext) -> Step:
    data = load(ctx)
    request = block_request(ctx, data, confirmed=True, state="EXECUTE_BLOCK")
    if request is None or data.product_id is None:
        return Step(CONFIRM_BLOCK)
    product_id, reason = data.product_id, data.block_reason or CardBlockReason.PRECAUTION

    async def run() -> SourceRef:
        product = await ctx.tools.block_card(product_id, request.idempotency_key, reason)
        return SourceRef.of(SourceTable.PRODUCTS, product.product_id)

    stop = await execute_writes(ctx, [PlannedWrite(request, "EXECUTE_BLOCK", run, card=_facts(data))], state=EXECUTE)
    return stop or Step(VERIFY)


async def verify(ctx: TurnContext) -> Step:
    data = load(ctx)
    request = block_request(ctx, data, confirmed=True, state="EXECUTE_BLOCK")
    if request is None or data.product_id is None:
        return Step(CONFIRM_BLOCK)
    product_id, verifier = data.product_id, ctx.write_verifier()
    check = ReadBack(ToolName.BLOCK_CARD, request.idempotency_key, lambda: verifier.card_blocked(product_id))
    stop = await verify_writes(ctx, [check])
    if stop is not None:
        return stop
    evidence = SourceRef.of(SourceTable.PRODUCTS, product_id)
    status = ActionStatusView(action=ActionKind.BLOCK_CARD, status=ActionDisplayStatus.VERIFIED, evidence=evidence)
    data = data.evolve(status=ProductStatus.BLOCKED, confirm_shown=False)
    save(ctx, data)
    if data.block_first and data.action is CardAction.REPLACEMENT_REQUEST:
        step = _handoff(ctx, data)
        if step.reply is not None:
            return replace(step, reply=replace(step.reply, action_statuses=(status,)))
        return step
    reply = Reply(
        template="card.blocked",
        params=_params(ctx, data),
        explain=(clause_ref(ctx, "INF-ALL-2"),),
        action_statuses=(status,),
    )
    return Step(RESOLVED, reply, Outcome.RESOLVED)
