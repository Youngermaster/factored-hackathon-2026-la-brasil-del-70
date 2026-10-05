"""Follow-ups to an account answer: after balances, a payment status, or a statement summary, a message that only
names a product, a card ending, or a period ("¿y nomás en la de ahorro?", "e da poupança só?", "y ahora el de
abril", "na verdade dos últimos 4 meses") continues the same inquiry instead of getting the workflow question."""

from bank_agent.application.engine.context import TurnContext
from bank_agent.application.understanding import extraction, slots
from bank_agent.application.understanding.periods import resolve_period
from bank_agent.domain.workflow import Intent

ACCOUNT_INTENTS = frozenset({Intent.BALANCE_INQUIRY, Intent.PAYMENT_STATUS, Intent.STATEMENT_REQUEST})


def follow_up(ctx: TurnContext) -> Intent | None:
    """The account intent the message continues, or ``None`` when it names no product, ending, or period."""
    intent = ctx.engine.intent
    if intent not in ACCOUNT_INTENTS:
        return None
    text = ctx.text
    named = slots.account_product_type(text) is not None or extraction.card_last4(text) is not None
    if named or resolve_period(text, ctx.today) is not None:
        return intent
    return None
