"""B0 dispute handlers: menu intent, the rule resolver's top candidate or a numbered list, and a fixed reason menu.

Everything else (eligibility, confirmation, execution, read-back, handoffs) is the proposed system's code, so the
comparison in phase 14 isolates understanding and dialogue, not policy or tools.
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.reply import Reply
from bank_agent.application.engine.shared import escalate, spend_clarification
from bank_agent.application.understanding import amounts, dates, extraction
from bank_agent.application.workflows.dispute.data import load, open_questions, save
from bank_agent.application.workflows.dispute.locate import _ask_options, _candidates
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.workflow import Intent, Outcome


async def understand(ctx: TurnContext) -> Step:
    data = load(ctx)
    intent = ctx.prediction.intent if ctx.prediction is not None else Intent.DISPUTE_NEW
    mention = amounts.best_amount(ctx.text)
    found = dates.resolve_dates(ctx.text, ctx.today)
    data = data.evolve(
        intent=Intent.DISPUTE_STATUS if intent is Intent.DISPUTE_STATUS else Intent.DISPUTE_NEW,
        amount=mention.amount if mention is not None else data.amount,
        date_expression=found.expression[:100] if found is not None else data.date_expression,
        date_options=found.interpretations[:1] if found is not None else data.date_options,
        merchant=extraction.merchant_phrase(ctx.text) or data.merchant,
        reason=extraction.dispute_reason(ctx.text) or data.reason,
    )
    save(ctx, data)
    return Step("STATUS_INQUIRY" if data.intent is Intent.DISPUTE_STATUS else "LOCATE_TRANSACTION")


async def locate(ctx: TurnContext) -> Step:
    data = load(ctx)
    candidates = await _candidates(ctx, data)
    resolution = ctx.services.resolver.rank(data.descriptor(), candidates, now=ctx.now.astimezone(ctx.zone))
    ctx.recorder.model(resolution.model)
    if resolution.clear_winner is not None:
        save(ctx, data.evolve(transaction_id=resolution.clear_winner, option_ids=()))
        return Step("CHECK_ELIGIBILITY")
    by_id = {txn.transaction_id: txn for txn in candidates}
    ranked = [by_id[candidate.transaction_id] for candidate in resolution.ranked]
    if not ranked:
        return escalate(ctx, EscalationReasonCode.OTHER, "baseline_no_candidate", open_questions=open_questions(data))
    stop = spend_clarification(ctx, open_questions=open_questions(data))
    return stop or await _ask_options(ctx, data, ranked)


async def classify_reason(ctx: TurnContext) -> Step:
    data = load(ctx)
    if data.reason is None and data.asked_reason and not ctx.reprompt:
        data = data.evolve(reason=extraction.dispute_reason(ctx.text))
    if data.reason is None:
        stop = spend_clarification(ctx, open_questions=open_questions(data))
        if stop is not None:
            return stop
        save(ctx, data.evolve(asked_reason=True))
        return Step("CLASSIFY_REASON", Reply(template="b0.reasons"), Outcome.CLARIFIED)
    save(ctx, data)
    return Step("CONFIRM_SUMMARY")
