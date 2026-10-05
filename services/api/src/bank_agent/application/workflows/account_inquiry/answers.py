"""BALANCES and PAYMENT_STATUS: read-only answers, each with the as-of date of its data.

Balances state the as-of instant of the balance records (``BalanceView.as_of``); payment answers state the data
as-of date from policy settings. The kernel checks ownership and that the as-of date is disclosed
(``ACC.product_owned_by_session_customer``, ``ACC.as_of_disclosed``) before anything is said, and every balance goes
to the grounding verifier as a balance fact next to its as-of fact. A customer who insists a balance is wrong is
handed to a person with the balances and their as-of date as verified facts.
"""

import re
from datetime import date, datetime, time

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import evaluate
from bank_agent.application.engine.reply import Masked, Param, RecordText, Reply
from bank_agent.application.engine.shared import blocking_step, clause_ref, escalate
from bank_agent.application.engine.templates.labels import PAYMENT_KINDS, PAYMENT_STATUSES, PRODUCT_TYPES, pick
from bank_agent.application.grounding.draft import FactKind, RecordFact
from bank_agent.application.tools.views import PaymentFilter
from bank_agent.application.understanding.text import fold
from bank_agent.application.workflows.account_inquiry.data import Choosing, load, save
from bank_agent.domain.accounts import PAYMENT_TYPES, BalanceView
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.workflow import Outcome
from bank_agent.policy.facts import AccountFacts

BALANCES = "BALANCES"
PAYMENT_STATUS = "PAYMENT_STATUS"
UNDERSTAND = "UNDERSTAND"
_CONTESTED = re.compile(
    r"\b(esta|estan) (mal|equivocad[oa]s?|errad[oa]s?)\b|\bno (es|esta|son) correct[oa]s?\b|\bincorrect[oa]s?\b|"
    r"\bno cuadra\b|\bno coincide\b|\bnao (esta|bate|confere|e) (certo|correto)?|\best(a|ao) errad[oa]s?\b|"
    r"\bsaldo errado\b|\bwrong balance\b|\bis wrong\b|"
    # Colloquial (QA 2026-10-05, ACC-08): "o saldo da poupança tá errado, era pra ter mais", "no me cierra".
    r"\b(ta|to|tah|tao)\s+errad[oa]s?\b|\bsaldo\b.{0,30}\berrad[oa]s?\b|"
    r"\b(era pra|era para|deveria) ter mais\b|\bdeberia (tener|haber) mas\b|\bno me cierra\b"
)


def contested(text: str) -> bool:
    return bool(_CONTESTED.search(fold(text)))


def _fact(kind: FactKind, **value: object) -> RecordFact:
    return RecordFact.model_validate({"fact_id": "x", "kind": kind, **value})


def _balance_item(ctx: TurnContext, view: BalanceView) -> tuple[dict[str, Param], tuple[RecordFact, ...]]:
    item: dict[str, Param] = {
        "type": pick(PRODUCT_TYPES[view.product_type], ctx.language),
        "card": Masked(view.masked_number.last4),
        "balance": view.current_balance,
    }
    facts = [_fact(FactKind.BALANCE, money=view.current_balance)]
    if view.available_credit is not None and view.credit_limit is not None:
        item["available"], item["limit"] = view.available_credit, view.credit_limit
        facts += [_fact(FactKind.AVAILABLE_CREDIT, money=view.available_credit),
                  _fact(FactKind.CREDIT_LIMIT, money=view.credit_limit)]  # fmt: skip
    return item, tuple(facts)


def _balance_fact(ctx: TurnContext, view: BalanceView, as_of: date) -> None:
    balance = view.current_balance
    text = f"{view.product_type.value} ending {view.masked_number.last4} balance {balance.amount} "
    text += f"{balance.currency.value} as of {as_of}"
    ctx.engine = ctx.engine.with_fact(text, view.product_ref)


async def balances(ctx: TurnContext) -> Step:
    data = load(ctx)
    if ctx.reprompt:
        return Step(BALANCES, Reply(template="account.anything_else"), Outcome.IN_PROGRESS)
    if data.answered and not contested(ctx.text):
        return Step(UNDERSTAND)
    views = list(await ctx.tools.list_my_balances())
    if data.hint_type is not None or data.hint_last4 is not None:
        chosen = [v for v in views if v.product_type is data.hint_type or v.masked_number.last4 == data.hint_last4]
        views = chosen or views
    if not views:
        return Step("RESOLVED", Reply(template="account.no_balances"), Outcome.RESOLVED)
    as_of_instant = max(view.as_of for view in views)
    as_of = as_of_instant.astimezone(ctx.zone).date()
    currencies = {view.current_balance.currency for view in views}
    ctx.currency = next(iter(currencies)) if len(currencies) == 1 else None
    decision = evaluate(ctx, account=AccountFacts(product_owned_by_session_customer=True, answer_as_of=as_of_instant))
    stop = blocking_step(ctx, decision, state=BALANCES)
    if stop is not None:
        return stop
    for view in views:
        _balance_fact(ctx, view, view.as_of.astimezone(ctx.zone).date())
    if contested(ctx.text):
        return escalate(ctx, EscalationReasonCode.UNSUPPORTED_NEEDS_HUMAN, "balance_contested", decision=decision,
                        open_questions=("Which balance does the customer consider wrong, and why?",))  # fmt: skip
    rows = [_balance_item(ctx, view) for view in views]
    lines = tuple(
        ("account.balance_item_credit" if "available" in row else "account.balance_item", row) for row, _ in rows
    )
    facts = (_fact(FactKind.AS_OF, at=as_of_instant.astimezone(ctx.zone)), *(f for _, fs in rows for f in fs))
    save(ctx, data.evolve(answered=True))
    reply = Reply(
        template="account.balances",
        params={"as_of": as_of},
        suffix=lines,
        explain=(clause_ref(ctx, "ACC-ALL-1"),),
        facts=facts,
        balances=tuple(views),
    )
    return Step(BALANCES, reply, Outcome.RESOLVED)


def reference_day(ctx: TurnContext) -> date:
    """The day relative expressions ("el mes pasado", "últimos 90 dias") count from: today, or the data as-of
    date when the data stops earlier, so a relative period never falls after the data (QA 2026-10-05, ACC-03)."""
    return min(ctx.today, ctx.services.policy.data_as_of)


def data_as_of(ctx: TurnContext) -> tuple[date, datetime]:
    """The data as-of date from policy settings, and the end of that day in the customer's time zone."""
    day = ctx.services.policy.data_as_of
    return day, datetime.combine(day, time(23, 59, 59), ctx.zone)


async def payment_status(ctx: TurnContext) -> Step:
    data = load(ctx)
    if ctx.reprompt:
        return Step(PAYMENT_STATUS, Reply(template="account.anything_else"), Outcome.IN_PROGRESS)
    if data.answered:
        return Step(UNDERSTAND)
    txn = await ctx.tools.get_transaction(data.transaction_id) if data.transaction_id is not None else None
    if txn is None or txn.transaction_type not in PAYMENT_TYPES:
        save(ctx, data.evolve(transaction_id=None, choosing=Choosing.NOTHING))
        return Step("LOCATE_PAYMENT")
    window = PaymentFilter(
        occurred_from=txn.occurred_at,
        occurred_to=txn.occurred_at,
        product_ids=(txn.product_id,),
        min_amount=txn.amount.amount,
        max_amount=txn.amount.amount,
    )
    views = await ctx.tools.get_payment_status(window)
    view = next((v for v in views if v.transaction_ref.key == txn.transaction_id), None)
    if view is None:
        save(ctx, data.evolve(transaction_id=None, choosing=Choosing.NOTHING))
        return Step("LOCATE_PAYMENT")
    as_of, as_of_instant = data_as_of(ctx)
    decision = evaluate(ctx, account=AccountFacts(product_owned_by_session_customer=True, answer_as_of=as_of_instant))
    stop = blocking_step(ctx, decision, state=PAYMENT_STATUS)
    if stop is not None:
        return stop
    ctx.engine = ctx.engine.with_fact(
        f"{view.transaction_type.value} of {view.amount.amount} {view.amount.currency.value} on {view.occurred_on} "
        f"is {view.status.value}",
        view.transaction_ref,
    )
    params: dict[str, Param] = {
        "kind": pick(PAYMENT_KINDS[view.transaction_type], ctx.language),
        "amount": view.amount,
        "date": view.occurred_on,
        "status": pick(PAYMENT_STATUSES[view.status], ctx.language),
        "as_of": as_of,
    }
    if view.payee_display:
        params["payee"] = RecordText(view.payee_display)
    save(ctx, data.evolve(answered=True))
    reply = Reply(
        template="account.payment_status" if view.payee_display else "account.payment_status_no_payee",
        params=params,
        explain=(clause_ref(ctx, "ACC-ALL-1"),),
        facts=(_fact(FactKind.AS_OF, day=as_of),),
        payment_statuses=(view,),
    )
    return Step(PAYMENT_STATUS, reply, Outcome.RESOLVED)
