"""STATEMENT_PERIOD and STATEMENT_SUMMARY: an activity summary of one product over a resolved period.

The period comes from the period table (``el mes pasado``, ``mês passado``, a month, the last N days or months). The
kernel's ``ACC.statement_period_within_limit`` decides whether it is missing, invalid, or longer than ``ACC-ALL-2``
allows; any of those asks again, against the clarification budget. The summary shows totals per currency for settled
operations and the counts of unclassified and unsettled ones, with the data as-of date. It never states an opening
or closing balance: the records do not hold statement balances.
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import evaluate, failed
from bank_agent.application.engine.reply import Masked, Param, Reply
from bank_agent.application.engine.shared import blocking_step, clause_ref
from bank_agent.application.engine.templates.labels import PRODUCT_OF_YOUR, pick
from bank_agent.application.grounding.draft import FactKind, RecordFact
from bank_agent.application.understanding.periods import resolve_period
from bank_agent.application.workflows.account_inquiry.answers import data_as_of, reference_day
from bank_agent.application.workflows.account_inquiry.data import AccountData, Choosing, exhausted, load, save
from bank_agent.application.workflows.account_inquiry.products import my_products
from bank_agent.domain.accounts import StatementSummary
from bank_agent.domain.workflow import Outcome
from bank_agent.policy.facts import AccountFacts

STATEMENT_PERIOD = "STATEMENT_PERIOD"
STATEMENT_SUMMARY = "STATEMENT_SUMMARY"
LIMIT_RULE = "ACC.statement_period_within_limit"


def _facts(ctx: TurnContext, data: AccountData) -> AccountFacts:
    period = data.period()
    days = (period.end - period.start).days + 1 if period is not None else None
    return AccountFacts(
        product_owned_by_session_customer=True, statement_period_days=days, answer_as_of=data_as_of(ctx)[1]
    )


def _ask(ctx: TurnContext, data: AccountData, *, unanswered: bool) -> Step:
    too_long = data.period() is not None
    template = "account.period_too_long" if too_long else "account.ask_period"
    save(ctx, data.evolve(asked_period=True))
    explain = (clause_ref(ctx, "ACC-ALL-2"),) if too_long else ()
    return Step(STATEMENT_PERIOD, Reply(template=template, explain=explain), Outcome.CLARIFIED, unanswered=unanswered)


async def statement_period(ctx: TurnContext) -> Step:
    data = load(ctx)
    if ctx.reprompt:
        return _ask(ctx, data, unanswered=False)
    answered_now = False
    if data.asked_period:
        period = resolve_period(ctx.text, reference_day(ctx))
        if period is not None:
            answered_now = True
            data = data.evolve(
                period_expression=period.expression[:100],
                period_start=period.dates.start,
                period_end=period.dates.end,
            )
    decision = evaluate(ctx, account=_facts(ctx, data))
    stop = blocking_step(ctx, decision, state=STATEMENT_PERIOD)
    if stop is not None:
        return stop
    if failed(decision, LIMIT_RULE):
        stop = exhausted(ctx, data)
        return stop or _ask(ctx, data, unanswered=data.asked_period and not answered_now)
    save(ctx, data.evolve(asked_period=False))
    return Step(STATEMENT_SUMMARY)


def _totals(summary: StatementSummary) -> tuple[tuple[tuple[str, dict[str, Param]], ...], tuple[RecordFact, ...]]:
    lines: list[tuple[str, dict[str, Param]]] = []
    facts: list[RecordFact] = []
    for totals in summary.totals:
        lines.append(
            ("account.statement_totals", {"currency": totals.currency.value, "debits": totals.debits,
                                          "credits": totals.credits})
        )  # fmt: skip
        for money in (totals.debits, totals.credits):
            facts.append(RecordFact(fact_id="t", kind=FactKind.STATEMENT_TOTAL, money=money))
    other: dict[str, Param] = {"unclassified": summary.unclassified_count, "unsettled": summary.not_settled_count}
    lines.append(("account.statement_other", other))
    return tuple(lines), tuple(facts)


async def statement_summary(ctx: TurnContext) -> Step:
    data = load(ctx)
    if ctx.reprompt:
        return Step(STATEMENT_SUMMARY, Reply(template="account.anything_else"), Outcome.IN_PROGRESS)
    if data.answered:
        return Step("UNDERSTAND")
    period = data.period()
    summary = await ctx.tools.get_statement_summary(data.product_id, period) if data.product_id and period else None
    product = next((p for p in await my_products(ctx) if p.product_id == data.product_id), None)
    if summary is None or product is None or period is None:
        save(ctx, data.evolve(product_id=None, choosing=Choosing.NOTHING))
        return Step("SELECT_PRODUCT")
    decision = evaluate(ctx, account=_facts(ctx, data))
    stop = blocking_step(ctx, decision, state=STATEMENT_SUMMARY)
    if stop is not None:
        return stop
    as_of = data_as_of(ctx)[0]
    ctx.engine = ctx.engine.with_fact(
        f"statement {period.start} to {period.end}: {summary.transaction_count} operations", product.ref
    )
    params: dict[str, Param] = {
        "of_type": pick(PRODUCT_OF_YOUR[product.product_type], ctx.language),
        "card": Masked(product.last4),
        "start": period.start,
        "end": period.end,
        "as_of": as_of,
        "count": summary.transaction_count,
    }
    save(ctx, data.evolve(answered=True))
    as_of_fact = RecordFact(fact_id="a", kind=FactKind.AS_OF, day=as_of)
    explain = (clause_ref(ctx, "ACC-ALL-2"),)
    if summary.transaction_count == 0:
        reply = Reply(
            template="account.statement_empty", params=params, explain=explain, facts=(as_of_fact,), statement=summary
        )
        return Step(STATEMENT_SUMMARY, reply, Outcome.RESOLVED)
    lines, facts = _totals(summary)
    reply = Reply(template="account.statement", params=params, suffix=lines, explain=explain,
                  facts=(as_of_fact, *facts), statement=summary)  # fmt: skip
    return Step(STATEMENT_SUMMARY, reply, Outcome.RESOLVED)
