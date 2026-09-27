"""CHECK_ELIGIBILITY, CLASSIFY_REASON, OFFER_PROTECTIVE_BLOCK, and CONFIRM_SUMMARY: the kernel decides over facts
read from the session's own records; deny reasons become customer explanations through the policy renderer."""

from datetime import timedelta

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import beyond_step_up, evaluate, explanation
from bank_agent.application.engine.definition import RESOLVED
from bank_agent.application.engine.idempotency import derive_key
from bank_agent.application.engine.reply import Masked, Param, RecordText, Reply
from bank_agent.application.engine.security import detect_injection
from bank_agent.application.engine.shared import abstain, blocking_step, escalate_decision
from bank_agent.application.engine.templates.labels import REASONS
from bank_agent.application.understanding.answers import YesNo, parse_yes_no
from bank_agent.application.understanding.extraction import dispute_reason
from bank_agent.application.workflows.dispute.data import BlockOffer, DisputeData, load, open_questions, save
from bank_agent.application.workflows.dispute.locate import exhausted
from bank_agent.domain.actions import ActionKind, ActionRequest, BlockCardArguments, CreateDisputeArguments
from bank_agent.domain.conversation import ConfirmationCard
from bank_agent.domain.decision import Decision, DecisionKind
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.identifiers import SourceRef, SourceTable
from bank_agent.domain.locale import Language
from bank_agent.domain.product import CARD_TYPES, ProductStatus
from bank_agent.domain.transaction import Transaction
from bank_agent.domain.workflow import Outcome
from bank_agent.policy.facts import CardFacts, DisputeFacts, TransactionFacts

CLASSIFY_REASON = "CLASSIFY_REASON"
OFFER_BLOCK = "OFFER_PROTECTIVE_BLOCK"
CONFIRM = "CONFIRM_SUMMARY"
EXECUTE = "EXECUTE"


async def transaction_facts(ctx: TurnContext, txn: Transaction) -> TransactionFacts:
    cases = await ctx.tools.list_my_cases()
    open_dispute = any(case.transaction_id == txn.transaction_id and case.is_open for case in cases)
    return TransactionFacts(
        owned_by_session_customer=True,
        status=txn.status,
        occurred_on=txn.occurred_at.astimezone(ctx.zone).date(),
        amount=txn.amount,
        has_open_dispute=open_dispute,
    )


async def dispute_facts(ctx: TurnContext, data: DisputeData) -> tuple[DisputeFacts, Transaction] | None:
    if data.transaction_id is None:
        return None
    txn = await ctx.tools.get_transaction(data.transaction_id)
    if txn is None:
        return None
    facts = await transaction_facts(ctx, txn)
    amount = data.disputed_amount or txn.amount
    return DisputeFacts(transaction=facts, reason=data.reason, disputed_amount=amount), txn


def denied(ctx: TurnContext, decision: Decision) -> Step:
    return abstain(ctx, "dispute.denied", explanation(decision))


async def check_eligibility(ctx: TurnContext) -> Step:
    data = load(ctx)
    found = await dispute_facts(ctx, data)
    if found is None:
        save(ctx, data.evolve(transaction_id=None))
        return Step("LOCATE_TRANSACTION")
    facts, txn = found
    local_day = facts.transaction.occurred_on if facts.transaction else ctx.today
    source = SourceRef.of(SourceTable.TRANSACTIONS, txn.transaction_id)
    amount = f"{txn.amount.amount} {txn.amount.currency.value}"
    ctx.engine = ctx.engine.with_fact(f"transaction of {amount} on {local_day} with status {txn.status.value}", source)
    product = await ctx.tools.get_product_status(txn.product_id)
    active_card = product is not None and product.product_type in CARD_TYPES
    data = data.evolve(
        product_id=txn.product_id,
        product_last4=product.masked_number.last4 if product is not None else None,
        card_active=active_card and product is not None and product.status is ProductStatus.ACTIVE,
        disputed_amount=facts.disputed_amount,
    )
    save(ctx, data)
    decision = evaluate(ctx, dispute=facts)
    stop = blocking_step(ctx, decision, state="CHECK_ELIGIBILITY")
    if stop is not None:
        return stop
    if decision.kind in (DecisionKind.DENY, DecisionKind.ABSTAIN):
        return denied(ctx, decision)
    return Step(CLASSIFY_REASON)


def _ask_reason(ctx: TurnContext, data: DisputeData, *, unanswered: bool = False) -> Step:
    save(ctx, data.evolve(asked_reason=True))
    return Step(CLASSIFY_REASON, Reply(template="dispute.ask_reason"), Outcome.CLARIFIED, unanswered=unanswered)


async def classify_reason(ctx: TurnContext) -> Step:
    data = load(ctx)
    if ctx.reprompt and data.reason is None:
        return _ask_reason(ctx, data)
    if data.reason is None and data.asked_reason:
        data = data.evolve(reason=dispute_reason(ctx.text))
        if data.reason is None:
            return exhausted(ctx, data) or _ask_reason(ctx, data, unanswered=True)
    if data.reason is None:
        return exhausted(ctx, data) or _ask_reason(ctx, data)
    save(ctx, data)
    found = await dispute_facts(ctx, data)
    if found is None:
        return Step("LOCATE_TRANSACTION")
    decision = evaluate(ctx, dispute=found[0])
    stop = blocking_step(ctx, decision, state=CLASSIFY_REASON)
    if stop is not None:
        return stop
    if decision.kind in (DecisionKind.DENY, DecisionKind.ABSTAIN):
        return denied(ctx, decision)
    wants_block = data.reason is DisputeReason.UNRECOGNIZED and data.card_active
    if wants_block and data.block_offer is BlockOffer.NONE:
        return Step(OFFER_BLOCK)
    return Step(CONFIRM)


def block_request(ctx: TurnContext, data: DisputeData, *, confirmed: bool, state: str) -> ActionRequest | None:
    if data.product_id is None:
        return None
    target = SourceRef.of(SourceTable.PRODUCTS, data.product_id)
    return ActionRequest(
        action=ActionKind.BLOCK_CARD,
        target=target,
        arguments=BlockCardArguments(product_id=data.product_id),
        idempotency_key=derive_key(ctx.conversation.conversation_id, target, ActionKind.BLOCK_CARD),
        requested_in_state=state,
        confirmed_at=ctx.now if confirmed else None,
    )


def case_request(ctx: TurnContext, data: DisputeData, *, confirmed: bool, state: str) -> ActionRequest | None:
    if data.transaction_id is None or data.reason is None or data.disputed_amount is None:
        return None
    target = SourceRef.of(SourceTable.TRANSACTIONS, data.transaction_id)
    arguments = CreateDisputeArguments(
        transaction_id=data.transaction_id, reason=data.reason, disputed_amount=data.disputed_amount
    )
    return ActionRequest(
        action=ActionKind.CREATE_DISPUTE_CASE,
        target=target,
        arguments=arguments,
        idempotency_key=derive_key(ctx.conversation.conversation_id, target, ActionKind.CREATE_DISPUTE_CASE),
        requested_in_state=state,
        confirmed_at=ctx.now if confirmed else None,
    )


def card_facts(data: DisputeData) -> CardFacts:
    status = ProductStatus.ACTIVE if data.card_active else ProductStatus.BLOCKED
    return CardFacts(owned_by_session_customer=True, is_card=True, status=status)


async def offer_block(ctx: TurnContext) -> Step:
    data = load(ctx)
    last4 = Masked(data.product_last4 or "----")
    if data.block_offer is BlockOffer.OFFERED and not ctx.reprompt:
        answer = parse_yes_no(ctx.text)
        if answer is YesNo.UNCLEAR:
            reply = Reply(template="dispute.offer_block", params={"card": last4})
            return exhausted(ctx, data) or Step(OFFER_BLOCK, reply, Outcome.CLARIFIED, unanswered=True)
        offer = BlockOffer.ACCEPTED if answer is YesNo.YES else BlockOffer.DECLINED
        save(ctx, data.evolve(block_offer=offer))
        return Step(CONFIRM)
    request = block_request(ctx, data, confirmed=False, state="OFFER_CARD_BLOCK")
    decision = evaluate(ctx, action=request, card=card_facts(data))
    stop = blocking_step(ctx, decision, state=OFFER_BLOCK, step_up_ok=True)
    if stop is not None:
        return stop
    if beyond_step_up(decision) in (DecisionKind.DENY, DecisionKind.ABSTAIN):
        save(ctx, data.evolve(block_offer=BlockOffer.SKIPPED))
        return Step(CONFIRM)
    save(ctx, data.evolve(block_offer=BlockOffer.OFFERED))
    crd2 = ctx.services.policy.pack.get_clause("CRD-ALL-2", Language.ES).ref
    return Step(OFFER_BLOCK, Reply(template="dispute.offer_block", params={"card": last4}, explain=(crd2,)))


def _sla_days(ctx: TurnContext) -> int:
    value = ctx.bound("CONFIRM_DISPUTE").params(f"DSP-{ctx.customer.country.value}-2")["resolution_sla_days"]
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


async def _summary(ctx: TurnContext, data: DisputeData, txn: Transaction, *, unanswered: bool = False) -> Step:
    language = Language.ES if ctx.language is Language.EN else ctx.language
    reason = data.reason or DisputeReason.OTHER
    due = ctx.today + timedelta(days=_sla_days(ctx))
    blocking = data.block_offer is BlockOffer.ACCEPTED
    params: dict[str, Param] = {
        "date": txn.occurred_at.astimezone(ctx.zone).date(),
        "merchant": RecordText(txn.merchant_name or "-"),
        "amount": data.disputed_amount or txn.amount,
        "card": Masked(data.product_last4 or "----"),
        "reason": REASONS[reason][language],
        "due": due,
    }
    planned = (ActionKind.BLOCK_CARD, ActionKind.CREATE_DISPUTE_CASE) if blocking else (ActionKind.CREATE_DISPUTE_CASE,)
    card = ConfirmationCard(
        occurred_on=txn.occurred_at.astimezone(ctx.zone).date(),
        merchant_display=(txn.merchant_name or "")[:150] or None,
        amount=data.disputed_amount or txn.amount,
        card_last4=data.product_last4,
        reason=reason,
        planned_actions=planned,
        expected_resolution_by=due,
    )
    if txn.merchant_name and detect_injection(txn.merchant_name):
        ctx.recorder.intervention("record_text_injection_flagged")
    save(ctx, data.evolve(summary_shown=True))
    template = "dispute.confirm_with_block" if blocking else "dispute.confirm"
    reply = Reply(
        template=template, params=params, confirmation=card, prefix="common.confirm_again" if unanswered else None
    )
    return Step(CONFIRM, reply, Outcome.IN_PROGRESS, unanswered=unanswered)


async def confirm_summary(ctx: TurnContext) -> Step:
    data = load(ctx)
    found = await dispute_facts(ctx, data)
    if found is None:
        return Step("LOCATE_TRANSACTION")
    facts, txn = found
    if data.summary_shown and not ctx.reprompt:
        answer = parse_yes_no(ctx.text)
        if answer is YesNo.YES:
            return Step(EXECUTE)
        if answer is YesNo.NO:
            save(ctx, data.evolve(summary_shown=False))
            return Step(RESOLVED, Reply(template="common.nothing_recorded"), Outcome.RESOLVED)
        return exhausted(ctx, data) or await _summary(ctx, data, txn, unanswered=True)
    decision = evaluate(ctx, dispute=facts)
    stop = blocking_step(ctx, decision, state=CONFIRM, step_up_ok=True)
    if stop is not None:
        return stop
    if decision.kind in (DecisionKind.DENY, DecisionKind.ABSTAIN):
        return denied(ctx, decision)
    return await _summary(ctx, data, txn)


def escalate_with_facts(ctx: TurnContext, decision: Decision) -> Step:
    return escalate_decision(ctx, decision, open_questions=open_questions(load(ctx)))
