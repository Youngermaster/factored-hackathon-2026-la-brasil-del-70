"""SELECT_PRODUCT and CLARIFY for account inquiries: which of the customer's own products, and which payment.

SELECT_PRODUCT lists only the session customer's products (``list_my_balances`` and ``list_my_cards``); a type or an
ending narrows the choice, and more than one plausible product is asked with masked options (type and last four).
CLARIFY parses the answer to the pending question (a product, a payment option, or payment details). Every
question counts against the clarification budget; once it is spent the kernel escalates.
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.reply import Choices, Masked, Param, Reply
from bank_agent.application.engine.templates.labels import PRODUCT_TYPES, pick
from bank_agent.application.understanding.answers import parse_choice
from bank_agent.application.understanding.text import fold
from bank_agent.application.workflows.account_inquiry.data import AccountData, Choosing, exhausted, load, save
from bank_agent.application.workflows.account_inquiry.payments import clarify_payment
from bank_agent.application.workflows.account_inquiry.products import ProductOption, my_products, narrowed
from bank_agent.domain.workflow import Outcome

CLARIFY = "CLARIFY"
STATEMENT_PERIOD = "STATEMENT_PERIOD"
LOCATE_PAYMENT = "LOCATE_PAYMENT"


def _options_reply(ctx: TurnContext, options: list[ProductOption], *, unanswered: bool = False) -> Step:
    items: tuple[dict[str, Param], ...] = tuple(
        {"type": pick(PRODUCT_TYPES[o.product_type], ctx.language), "card": Masked(o.last4)} for o in options
    )
    reply = Reply(template="account.clarify_product", params={"options": Choices("account.product_option", items)})
    return Step(CLARIFY, reply, Outcome.CLARIFIED, unanswered=unanswered)


def _chosen(ctx: TurnContext, data: AccountData, option: ProductOption) -> Step:
    save(ctx, data.evolve(product_id=option.product_id, choosing=Choosing.NOTHING, option_ids=()))
    return Step(STATEMENT_PERIOD)


async def select_product(ctx: TurnContext) -> Step:
    data = load(ctx)
    products = await my_products(ctx)
    if data.product_id is not None:
        current = next((p for p in products if p.product_id == data.product_id), None)
        if current is not None:
            return _chosen(ctx, data, current)
    if not products:
        return Step("RESOLVED", Reply(template="account.no_balances"), Outcome.RESOLVED)
    plausible = narrowed(data, products)
    if len(plausible) == 1:
        return _chosen(ctx, data, plausible[0])
    stop = exhausted(ctx, data)
    if stop is not None:
        return stop
    save(ctx, data.evolve(choosing=Choosing.PRODUCT, option_ids=tuple(p.ref.key for p in plausible)))
    return _options_reply(ctx, plausible)


async def clarify(ctx: TurnContext) -> Step:
    data = load(ctx)
    if data.choosing is Choosing.PRODUCT:
        return await _clarify_product(ctx, data)
    return await clarify_payment(ctx, data)


async def _clarify_product(ctx: TurnContext, data: AccountData) -> Step:
    products = {p.ref.key: p for p in await my_products(ctx)}
    options = [products[key] for key in data.option_ids if key in products]
    if ctx.reprompt:
        return _options_reply(ctx, options)

    def matches(folded: str, option: ProductOption) -> bool:
        label = fold(pick(PRODUCT_TYPES[option.product_type], ctx.language))
        return option.last4 in folded.split() or any(w in folded for w in label.split() if len(w) > 5)

    index = parse_choice(ctx.text, options, matches)
    if index is None:
        stop = exhausted(ctx, data)
        return stop or _options_reply(ctx, options, unanswered=True)
    return _chosen(ctx, data, options[index])
