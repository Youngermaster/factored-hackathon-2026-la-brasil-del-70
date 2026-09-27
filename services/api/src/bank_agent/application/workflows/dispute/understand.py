"""UNDERSTAND for disputes: the router's intent, ``extract_dispute_slots`` through the gateway, and deterministic
normalization of amounts, slang, relative dates, the card ending, the channel, and the reason.

The model proposes; deterministic code decides. The normalized amount wins over the model's plain number when the
text holds a multiplier or a currency marker, dates are always interpreted by the date table (the model returns the
customer's words only), and every slot the model returns is validated by its output model before it is used.
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.llm import EXTRACT_DISPUTE, structured
from bank_agent.application.understanding import amounts, dates, extraction
from bank_agent.application.workflows.dispute.data import DisputeData, load, save
from bank_agent.domain.llm_outputs import DisputeSlotExtraction
from bank_agent.domain.workflow import Intent

DISPUTE_INTENTS = frozenset({Intent.DISPUTE_NEW, Intent.DISPUTE_STATUS})
STATUS_INQUIRY = "STATUS_INQUIRY"
LOCATE_TRANSACTION = "LOCATE_TRANSACTION"


async def absorb(ctx: TurnContext, data: DisputeData, text: str, *, use_model: bool = True) -> DisputeData:
    """Merge what ``text`` says into ``data``; slots already known are kept unless the text restates them."""
    model: DisputeSlotExtraction | None = None
    if use_model:
        variables = {
            "customer_message": ctx.text,
            "reference_date": ctx.today.isoformat(),
            "dialect_hint": ctx.locale.value,
        }
        model = await structured(ctx, EXTRACT_DISPUTE, variables, DisputeSlotExtraction)
    extracted = model.transaction if model is not None else None
    changes: dict[str, object] = {}
    mention = amounts.best_amount(text)
    if mention is not None and (mention.has_multiplier or mention.local_unit or mention.currency or not extracted):
        changes["amount"] = mention.amount
        changes["currency"] = amounts.resolve_currency(mention, frozenset({ctx.currency} if ctx.currency else ()))
    elif extracted is not None and extracted.amount is not None:
        changes["amount"], changes["currency"] = extracted.amount, extracted.currency_hint
    found = dates.resolve_dates(text, ctx.today)
    if found is None and extracted is not None and extracted.date_expression:
        found = dates.resolve_dates(extracted.date_expression, ctx.today)
    if found is not None:
        changes["date_expression"] = found.expression[:100]
        changes["date_options"] = found.interpretations
        changes["asked_date"] = False
    merchant = (extracted.merchant_text if extracted is not None else None) or extraction.merchant_phrase(text)
    if merchant:
        changes["merchant"] = merchant[:150]
    last4 = (extracted.card_last4_hint if extracted is not None else None) or extraction.card_last4(text)
    if last4:
        changes["card_last4"] = last4
    channel = (extracted.channel_hint if extracted is not None else None) or extraction.channel(text)
    if channel is not None:
        changes["channel"] = channel
    reason = extraction.dispute_reason(text)
    if reason is None and model is not None and model.reason_candidates:
        reason = model.reason_candidates[0]
    if reason is not None:
        changes["reason"] = reason
    if model is not None and data.intent is None:
        intents = [c.intent for c in model.intent_candidates if c.intent in DISPUTE_INTENTS]
        if intents:
            changes["intent"] = intents[0]
    return data.evolve(**changes) if changes else data


async def understand(ctx: TurnContext) -> Step:
    data = load(ctx)
    routed = ctx.prediction.intent if ctx.prediction is not None else None
    if routed in DISPUTE_INTENTS:
        data = data.evolve(intent=routed)
    data = await absorb(ctx, data, ctx.text)
    if data.intent is None:
        data = data.evolve(intent=Intent.DISPUTE_NEW)
    ctx.engine = ctx.engine.evolve(intent=data.intent)
    save(ctx, data)
    return Step(STATUS_INQUIRY if data.intent is Intent.DISPUTE_STATUS else LOCATE_TRANSACTION)
