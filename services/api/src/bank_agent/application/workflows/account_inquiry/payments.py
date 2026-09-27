"""LOCATE_PAYMENT, the payment answers of CLARIFY, and PAYMENT_STATUS.

LOCATE_PAYMENT ranks the session customer's own payments and transfers (``list_recent_transactions`` with the type
filter, within the ``ACC-ALL-2`` window before the data as-of date) through the ``TransactionResolver`` port, with the
same rules as LOCATE_TRANSACTION: a clear winner proceeds, otherwise two or three masked options, or a request for
detail when nothing matches what the customer said. PAYMENT_STATUS answers from ``get_payment_status`` with the data
as-of date. A payment that looks unauthorized is a ``dispute_new`` intent, so the router asks before switching.
"""

from datetime import UTC, datetime, time, timedelta

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.render import clean_record_text
from bank_agent.application.engine.reply import Choices, Masked, Param, RecordText, Reply
from bank_agent.application.understanding.answers import parse_choice
from bank_agent.application.workflows.account_inquiry.data import AccountData, Choosing, exhausted, load, save
from bank_agent.application.workflows.account_inquiry.understand import absorb
from bank_agent.application.workflows.dispute.locate import Matcher
from bank_agent.domain.accounts import PAYMENT_TYPES
from bank_agent.domain.identifiers import ProductId, TransactionId
from bank_agent.domain.transaction import Transaction
from bank_agent.domain.workflow import Outcome
from bank_agent.ports.repositories.transactions import MAX_TRANSACTION_PAGE, TransactionQuery

CLARIFY = "CLARIFY"
PAYMENT_STATUS = "PAYMENT_STATUS"
LOCATE_PAYMENT = "LOCATE_PAYMENT"
MAX_OPTIONS = 3


def window_start(ctx: TurnContext) -> datetime:
    value = ctx.bound("ANSWER_STATEMENT").params("ACC-ALL-2")["max_statement_days"]
    days = value if isinstance(value, int) and not isinstance(value, bool) else 0
    return datetime.combine(ctx.services.policy.data_as_of - timedelta(days=days), time.min, UTC)


async def _last4(ctx: TurnContext) -> dict[ProductId, str]:
    found = {ProductId(b.product_ref.key): b.masked_number.last4 for b in await ctx.tools.list_my_balances()}
    for card in await ctx.tools.list_my_cards():
        found.setdefault(ProductId(card.product_ref.key), card.masked_number.last4)
    return found


async def _candidates(ctx: TurnContext, data: AccountData) -> list[Transaction]:
    query = TransactionQuery(
        occurred_from=window_start(ctx), types=tuple(sorted(PAYMENT_TYPES)), limit=MAX_TRANSACTION_PAGE
    )
    found = list(await ctx.tools.list_recent_transactions(query))
    currencies = {txn.amount.currency for txn in found}
    ctx.currency = next(iter(currencies)) if len(currencies) == 1 else None
    if data.hint_last4 is not None:
        last4 = await _last4(ctx)
        found = [txn for txn in found if last4.get(txn.product_id) == data.hint_last4] or found
    return found


def _described(data: AccountData) -> bool:
    return data.amount is not None or bool(data.payee) or bool(data.date_options)


async def _ask_options(ctx: TurnContext, data: AccountData, ranked: list[Transaction]) -> Step:
    last4 = await _last4(ctx)
    items: tuple[dict[str, Param], ...] = tuple(
        {"date": txn.occurred_at.astimezone(ctx.zone).date(),
         "payee": RecordText(clean_record_text(txn.merchant_name or "") or "-"),
         "amount": txn.amount, "card": Masked(last4.get(txn.product_id, "----"))}
        for txn in ranked[:MAX_OPTIONS]
    )  # fmt: skip
    save(ctx, data.evolve(choosing=Choosing.PAYMENT, option_ids=tuple(t.transaction_id for t in ranked[:MAX_OPTIONS])))
    reply = Reply(template="account.clarify_payment", params={"options": Choices("account.payment_option", items)})
    return Step(CLARIFY, reply, Outcome.CLARIFIED)


def _ask_details(ctx: TurnContext, data: AccountData) -> Step:
    save(ctx, data.evolve(choosing=Choosing.PAYMENT_DETAILS, option_ids=()))
    return Step(CLARIFY, Reply(template="account.ask_payment_details"), Outcome.CLARIFIED)


async def locate_payment(ctx: TurnContext) -> Step:
    data = load(ctx)
    if ctx.referenced_transaction is not None:
        save(ctx, data.evolve(transaction_id=ctx.referenced_transaction, choosing=Choosing.NOTHING))
        return Step(PAYMENT_STATUS)
    candidates = await _candidates(ctx, data)
    resolution = ctx.services.resolver.rank(data.descriptor(), candidates, now=ctx.now.astimezone(ctx.zone))
    ctx.recorder.model(resolution.model)
    winner = resolution.clear_winner
    if winner is None and not _described(data) and len(candidates) == 1:
        winner = candidates[0].transaction_id
    if winner is not None:
        save(ctx, data.evolve(transaction_id=winner, choosing=Choosing.NOTHING, option_ids=()))
        return Step(PAYMENT_STATUS)
    by_id = {txn.transaction_id: txn for txn in candidates}
    ranked = [by_id[candidate.transaction_id] for candidate in resolution.ranked]
    if not ranked and not _described(data):
        ranked = sorted(candidates, key=lambda txn: (txn.occurred_at, txn.transaction_id), reverse=True)
    stop = exhausted(ctx, data)
    if stop is not None:
        return stop
    return await _ask_options(ctx, data, ranked) if ranked else _ask_details(ctx, data)


async def clarify_payment(ctx: TurnContext, data: AccountData) -> Step:
    if data.choosing is Choosing.PAYMENT_DETAILS:
        if ctx.reprompt:
            return _ask_details(ctx, data)
        save(ctx, await absorb(ctx, data, ctx.text))
        return Step(LOCATE_PAYMENT)
    ids = [TransactionId(key) for key in data.option_ids]
    found = {txn_id: await ctx.tools.get_transaction(txn_id) for txn_id in ids}
    known = {txn_id: txn for txn_id, txn in found.items() if txn is not None}
    options = [txn_id for txn_id in ids if txn_id in known]
    if ctx.reprompt:
        return await _ask_options(ctx, data, [known[i] for i in options])
    index = parse_choice(ctx.text, options, Matcher(ctx, known))
    if index is None:
        stop = exhausted(ctx, data)
        if stop is not None:
            return stop
        asked = await _ask_options(ctx, data, [known[i] for i in options])
        return Step(CLARIFY, asked.reply, Outcome.CLARIFIED, unanswered=True)
    save(ctx, data.evolve(transaction_id=options[index], choosing=Choosing.NOTHING, option_ids=()))
    return Step(PAYMENT_STATUS)
