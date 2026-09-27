"""B0 account inquiry handlers: keyword slots only (no model) and the rule resolver's winner or a numbered list.

Balances, payment status, statements, the kernel, and the verifier are the proposed system's code, so the phase 14
comparison isolates understanding and dialogue.
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.shared import abstain_unsupported, escalate
from bank_agent.application.workflows.account_inquiry.data import AccountData, exhausted, load, open_questions, save
from bank_agent.application.workflows.account_inquiry.payments import _ask_options, _candidates
from bank_agent.application.workflows.account_inquiry.understand import ACCOUNT_INTENTS, NEXT_STATE, absorb
from bank_agent.application.workflows.account_inquiry.unsupported import recognize
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.workflow import Intent


async def understand(ctx: TurnContext) -> Step:
    request = recognize(ctx.text)
    if request is not None:
        return abstain_unsupported(ctx, request)
    routed = ctx.prediction.intent if ctx.prediction is not None else None
    intent = routed if routed in ACCOUNT_INTENTS else Intent.BALANCE_INQUIRY
    data = await absorb(ctx, AccountData(intent=intent), ctx.text, use_model=False)
    ctx.engine = ctx.engine.evolve(intent=intent)
    save(ctx, data)
    return Step(NEXT_STATE[intent])


async def locate_payment(ctx: TurnContext) -> Step:
    data = load(ctx)
    candidates = await _candidates(ctx, data)
    resolution = ctx.services.resolver.rank(data.descriptor(), candidates, now=ctx.now.astimezone(ctx.zone))
    ctx.recorder.model(resolution.model)
    if resolution.clear_winner is not None:
        save(ctx, data.evolve(transaction_id=resolution.clear_winner, option_ids=()))
        return Step("PAYMENT_STATUS")
    by_id = {txn.transaction_id: txn for txn in candidates}
    ranked = [by_id[candidate.transaction_id] for candidate in resolution.ranked]
    if not ranked:
        return escalate(ctx, EscalationReasonCode.OTHER, "baseline_no_candidate", open_questions=open_questions(data))
    stop = exhausted(ctx, data)
    return stop or await _ask_options(ctx, data, ranked)
