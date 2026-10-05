"""LOCATE_TRANSACTION and CLARIFY: rank the session customer's own transactions within the dispute window.

A clear winner above the resolver's margin proceeds. Otherwise CLARIFY shows two or three masked options (date,
merchant, amount, card ending); no candidate asks for more detail. An ambiguous day and month order is asked first.
Every question counts against the clarification budget; once it is spent the kernel escalates.
"""

from datetime import UTC, datetime, time, timedelta

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.render import clean_record_text
from bank_agent.application.engine.reply import Choices, Masked, Param, RecordText, Reply
from bank_agent.application.engine.security import detect_injection
from bank_agent.application.engine.shared import abstain, clause_ref, spend_clarification
from bank_agent.application.understanding.answers import YesNo, parse_choice, parse_yes_no
from bank_agent.application.understanding.dates import MONTHS, narrow
from bank_agent.application.understanding.text import words
from bank_agent.application.workflows.dispute.data import DisputeData, load, open_questions, save
from bank_agent.application.workflows.dispute.understand import absorb
from bank_agent.domain.conversation import Clarification, ClarificationOption
from bank_agent.domain.identifiers import ProductId, TransactionId
from bank_agent.domain.intelligence import DateRange
from bank_agent.domain.transaction import Transaction
from bank_agent.domain.workflow import Outcome
from bank_agent.ports.repositories.transactions import MAX_TRANSACTION_PAGE, TransactionQuery

CHECK_ELIGIBILITY = "CHECK_ELIGIBILITY"
CLARIFY = "CLARIFY"
LOCATE = "LOCATE_TRANSACTION"
MAX_OPTIONS = 3


def window_days(ctx: TurnContext) -> int:
    value = ctx.bound("COLLECT_DETAILS").params(f"DSP-{ctx.customer.country.value}-1")["dispute_window_days"]
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def window_start(ctx: TurnContext) -> datetime:
    start = ctx.services.policy.data_as_of - timedelta(days=window_days(ctx))
    return datetime.combine(start, time.min, UTC)


def exhausted(ctx: TurnContext, data: DisputeData) -> Step | None:
    """The escalation when no clarifying question is left, else ``None`` (and one more question is counted)."""
    save(ctx, data)
    return spend_clarification(ctx, open_questions=open_questions(data))


async def _last4_by_product(ctx: TurnContext) -> dict[ProductId, str]:
    cards = await ctx.tools.list_my_cards()
    return {ProductId(card.product_ref.key): card.masked_number.last4 for card in cards}


MAX_LOOKBACK_DAYS = 400


def before_window(ctx: TurnContext, data: DisputeData) -> bool:
    """Every date reading the customer gave ends before the dispute window opens."""
    start = window_start(ctx).date()
    return bool(data.date_options) and all(option.end < start for option in data.date_options)


async def _candidates(ctx: TurnContext, data: DisputeData) -> list[Transaction]:
    start = window_start(ctx)
    if before_window(ctx, data):
        # Search back to the stated date, so the kernel's DSP.within_window rule decides on the real transaction and
        # the reply cites the window clause instead of asking for details again (QA 2026-10-05).
        earliest = datetime.combine(min(o.start for o in data.date_options), time.min, UTC) - timedelta(days=2)
        start = max(earliest, start - timedelta(days=MAX_LOOKBACK_DAYS))
    query = TransactionQuery(occurred_from=start, limit=MAX_TRANSACTION_PAGE)
    found = list(await ctx.tools.list_recent_transactions(query))
    currencies = {txn.amount.currency for txn in found}
    ctx.currency = next(iter(currencies)) if len(currencies) == 1 else None
    carried = ctx.engine.carried_card
    if carried is not None:
        found = [txn for txn in found if txn.product_id == carried.key] or found
    if data.card_last4 is not None:
        last4 = await _last4_by_product(ctx)
        found = [txn for txn in found if last4.get(txn.product_id) == data.card_last4] or found
    return found


def _ask_date(ctx: TurnContext, data: DisputeData) -> Step:
    first, second = data.date_options[0].start, data.date_options[1].start
    params: dict[str, Param] = {"expression": RecordText(data.date_expression or ""), "first": first, "second": second}
    save(ctx, data.evolve(asked_date=True, option_ids=()))
    return Step(CLARIFY, Reply(template="dispute.clarify_date", params=params), Outcome.CLARIFIED)


async def _ask_options(ctx: TurnContext, data: DisputeData, ranked: list[Transaction]) -> Step:
    last4 = await _last4_by_product(ctx)
    options: list[ClarificationOption] = []
    items: list[dict[str, Param]] = []
    for index, txn in enumerate(ranked[:MAX_OPTIONS], 1):
        occurred_on = txn.occurred_at.astimezone(ctx.zone).date()
        merchant = clean_record_text(txn.merchant_name or "")
        if txn.merchant_name and detect_injection(txn.merchant_name):
            ctx.recorder.intervention("record_text_injection_flagged")
        card = last4.get(txn.product_id)
        options.append(
            ClarificationOption(
                option_id=f"opt-{index}",
                occurred_on=occurred_on,
                merchant_display=merchant or None,
                amount=txn.amount,
                card_last4=card,
            )
        )
        items.append({"date": occurred_on, "merchant": RecordText(merchant or "-"), "amount": txn.amount,
                      "card": Masked(card or "----")})  # fmt: skip
    save(ctx, data.evolve(option_ids=tuple(txn.transaction_id for txn in ranked[:MAX_OPTIONS]), asked_details=False))
    reply = Reply(
        template="dispute.clarify_one" if len(items) == 1 else "dispute.clarify_options",
        params={"options": Choices("dispute.option", tuple(items))},
        clarification=Clarification(options=tuple(options)),
    )
    return Step(CLARIFY, reply, Outcome.CLARIFIED)


def _ask_details(ctx: TurnContext, data: DisputeData) -> Step:
    save(ctx, data.evolve(asked_details=True, option_ids=()))
    return Step(CLARIFY, Reply(template="dispute.ask_details"), Outcome.CLARIFIED)


async def locate(ctx: TurnContext) -> Step:
    data = load(ctx)
    if ctx.referenced_transaction is not None:
        save(ctx, data.evolve(transaction_id=ctx.referenced_transaction, option_ids=()))
        return Step(CHECK_ELIGIBILITY)
    today, start = ctx.today, window_start(ctx).date()
    if len(data.date_options) > 1:
        data = data.evolve(date_options=narrow(data.date_options, start, today) or data.date_options)
        if len(data.date_options) > 1:
            return exhausted(ctx, data) or _ask_date(ctx, data)
    candidates = await _candidates(ctx, data)
    resolution = ctx.services.resolver.rank(data.descriptor(), candidates, now=ctx.now.astimezone(ctx.zone))
    ctx.recorder.model(resolution.model)
    if resolution.clear_winner is not None:
        save(ctx, data.evolve(transaction_id=resolution.clear_winner, option_ids=()))
        return Step(CHECK_ELIGIBILITY)
    by_id = {txn.transaction_id: txn for txn in candidates}
    ranked = [by_id[candidate.transaction_id] for candidate in resolution.ranked]
    stop = exhausted(ctx, data)
    if stop is not None:
        return stop
    if ranked:
        return await _ask_options(ctx, data, ranked)
    if before_window(ctx, data):
        clause = clause_ref(ctx, f"DSP-{ctx.customer.country.value}-1")
        return abstain(ctx, "dispute.denied", (clause,))
    return _ask_details(ctx, data)


class Matcher:
    """Match a free answer to one option by amount, merchant words, or day of the month."""

    def __init__(self, ctx: TurnContext, transactions: dict[TransactionId, Transaction]) -> None:
        self._ctx, self._transactions = ctx, transactions

    def __call__(self, folded: str, option: TransactionId) -> bool:
        txn = self._transactions[option]
        spoken = set(folded.split())
        amount = format(txn.amount.amount, "f").split(".")[0]
        merchant = {word for word in words(txn.merchant_name or "") if len(word) > 3}
        day = str(txn.occurred_at.astimezone(self._ctx.zone).day)
        return amount in spoken or bool(merchant & spoken) or f"el {day}" in folded or f"dia {day}" in folded


async def clarify(ctx: TurnContext) -> Step:
    data = load(ctx)
    if ctx.reprompt:
        if data.option_ids:
            return await _reprompt_options(ctx, data)
        return _ask_date(ctx, data) if data.asked_date and len(data.date_options) > 1 else _ask_details(ctx, data)
    if data.asked_date and len(data.date_options) > 1:
        return _choose_date(ctx, data)
    if data.option_ids:
        transactions = {txn_id: await ctx.tools.get_transaction(txn_id) for txn_id in data.option_ids}
        known = {txn_id: txn for txn_id, txn in transactions.items() if txn is not None}
        index = parse_choice(ctx.text, [i for i in data.option_ids if i in known], Matcher(ctx, known))
        if index is None and len(known) == 1:
            # One candidate is shown as "is it this one?": a yes picks it, a no asks for more details.
            answer = parse_yes_no(ctx.text)
            if answer is YesNo.YES:
                index = 0
            elif answer is YesNo.NO:
                return exhausted(ctx, data) or _ask_details(ctx, data)
        if index is not None:
            chosen = [i for i in data.option_ids if i in known][index]
            save(ctx, data.evolve(transaction_id=chosen, option_ids=()))
            return Step(CHECK_ELIGIBILITY)
        stop = exhausted(ctx, data)
        return stop or Step(CLARIFY, (await _reprompt_options(ctx, data)).reply, Outcome.CLARIFIED, unanswered=True)
    save(ctx, await absorb(ctx, data, ctx.text))
    return Step(LOCATE)


def _month_matches(folded: str, option: DateRange) -> bool:
    return any(name in folded.split() and number == option.start.month for name, number in MONTHS.items())


def _choose_date(ctx: TurnContext, data: DisputeData) -> Step:
    index = parse_choice(ctx.text, list(data.date_options), _month_matches)
    if index is None:
        stop = exhausted(ctx, data)
        return stop or Step(CLARIFY, _ask_date(ctx, data).reply, Outcome.CLARIFIED, unanswered=True)
    chosen: DateRange = data.date_options[index]
    save(ctx, data.evolve(date_options=(chosen,), asked_date=False))
    return Step(LOCATE)


async def _reprompt_options(ctx: TurnContext, data: DisputeData) -> Step:
    transactions = [await ctx.tools.get_transaction(txn_id) for txn_id in data.option_ids]
    return await _ask_options(ctx, data, [txn for txn in transactions if txn is not None])
