"""UNDERSTAND for account inquiries: the router's intent, ``extract_account_inquiry_slots`` through the gateway with a
deterministic fallback, and the task 8 normalization for amounts, slang, and relative dates.

The model proposes; deterministic code decides: amounts with a multiplier or a currency marker come from the amount
table, dates and periods always come from the date and period tables (the model returns the customer's words only),
and an in-domain request the workflow does not handle is abstained with ``ACC-ALL-3`` before anything is read.
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.llm import EXTRACT_ACCOUNT, structured
from bank_agent.application.engine.shared import abstain_unsupported
from bank_agent.application.understanding import amounts, dates, extraction, slots
from bank_agent.application.understanding.periods import resolve_period
from bank_agent.application.workflows.account_inquiry.answers import reference_day
from bank_agent.application.workflows.account_inquiry.data import AccountData, save
from bank_agent.application.workflows.account_inquiry.unsupported import recognize
from bank_agent.domain.llm_outputs import AccountInquirySlotExtraction
from bank_agent.domain.workflow import Intent

ACCOUNT_INTENTS = frozenset({Intent.BALANCE_INQUIRY, Intent.PAYMENT_STATUS, Intent.STATEMENT_REQUEST})
NEXT_STATE = {
    Intent.BALANCE_INQUIRY: "BALANCES",
    Intent.PAYMENT_STATUS: "LOCATE_PAYMENT",
    Intent.STATEMENT_REQUEST: "SELECT_PRODUCT",
}


def _period(data: AccountData, text: str, ctx: TurnContext) -> AccountData:
    period = resolve_period(text, reference_day(ctx))
    if period is None:
        return data
    return data.evolve(
        period_expression=period.expression[:100], period_start=period.dates.start, period_end=period.dates.end
    )


async def absorb(ctx: TurnContext, data: AccountData, text: str, *, use_model: bool = True) -> AccountData:
    """Merge what ``text`` says into ``data``; slots already known are kept unless the text restates them."""
    model: AccountInquirySlotExtraction | None = None
    if use_model:
        variables = {
            "customer_message": ctx.text,
            "reference_date": reference_day(ctx).isoformat(),
            "dialect_hint": ctx.locale.value,
        }
        model = await structured(ctx, EXTRACT_ACCOUNT, variables, AccountInquirySlotExtraction)
    hint = model.product_hint if model is not None else None
    changes: dict[str, object] = {}
    product_type = slots.account_product_type(text) or (hint.product_type if hint is not None else None)
    if product_type is not None:
        changes["hint_type"] = product_type
    last4 = extraction.card_last4(text) or (hint.last4 if hint is not None else None)
    if last4:
        changes["hint_last4"] = last4
    payment = model.payment if model is not None else None
    mention = amounts.best_amount(text)
    if mention is not None:
        changes["amount"] = mention.amount
        changes["currency"] = amounts.resolve_currency(mention, frozenset({ctx.currency} if ctx.currency else ()))
    elif payment is not None and payment.amount is not None:
        changes["amount"], changes["currency"] = payment.amount, payment.currency_hint
    found = dates.resolve_dates(text, reference_day(ctx))
    if found is None and payment is not None and payment.date_expression:
        found = dates.resolve_dates(payment.date_expression, reference_day(ctx))
    if found is not None:
        changes["date_expression"] = found.expression[:100]
        changes["date_options"] = found.interpretations
    payee = (payment.payee_text if payment is not None else None) or extraction.merchant_phrase(text)
    if payee:
        changes["payee"] = payee[:150]
    data = data.evolve(**changes) if changes else data
    data = _period(data, text, ctx)
    if data.period() is None and model is not None and model.statement_period_expression:
        data = _period(data, model.statement_period_expression, ctx)
    return data


async def understand(ctx: TurnContext) -> Step:
    request = recognize(ctx.text)
    if request is not None:
        return abstain_unsupported(ctx, request)
    routed = ctx.prediction.intent if ctx.prediction is not None else None
    data = AccountData(intent=routed if routed in ACCOUNT_INTENTS else ctx.engine.intent)
    if data.intent not in ACCOUNT_INTENTS:
        data = data.evolve(intent=Intent.BALANCE_INQUIRY)
    data = await absorb(ctx, data, ctx.text)
    intent = data.intent or Intent.BALANCE_INQUIRY
    ctx.engine = ctx.engine.evolve(intent=intent)
    save(ctx, data)
    return Step(NEXT_STATE[intent])
