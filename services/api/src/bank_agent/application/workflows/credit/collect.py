"""COLLECT_APPLICATION_FACTS: the product, the amount, and (for a loan) the term the customer asks about.

Nothing is guessed: a missing amount or term is asked, against the clarification budget. A credit card has no term
(one month, the billing cycle, is recorded). The purpose is the customer's own words mapped to the catalog's codes,
else ``general_purpose``, and it is shown before anything is recorded. The catalog entry must exist in the customer's
country (``CRE.product_in_catalog``, ``CRE.offered_in_jurisdiction``); a mortgage never reaches the eligibility
service (information only).
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import evaluate
from bank_agent.application.engine.reply import Reply
from bank_agent.application.engine.shared import blocking_step
from bank_agent.application.workflows.credit.data import DEFAULT_PURPOSE, CreditData, exhausted, load, save
from bank_agent.application.workflows.credit.info import ask_product, detail, facts, product_of
from bank_agent.application.workflows.credit.understand import absorb
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.workflow import Outcome

COLLECT = "COLLECT_APPLICATION_FACTS"


def _ask(ctx: TurnContext, data: CreditData, template: str, *, unanswered: bool) -> Step:
    save(ctx, data.evolve(asked_facts=True))
    return Step(COLLECT, Reply(template=template), Outcome.CLARIFIED, unanswered=unanswered)


def _missing_template(data: CreditData, product_type: CreditProductType) -> str | None:
    needs_term = product_type is not CreditProductType.CREDIT_CARD and data.term_months is None
    if data.amount is None:
        return "credit.ask_amount_term" if needs_term else "credit.ask_amount"
    return "credit.ask_term" if needs_term else None


async def collect(ctx: TurnContext) -> Step:
    data = load(ctx)
    answered = False
    if data.asked_facts and not ctx.reprompt:
        before = (data.amount, data.term_months, data.product_type)
        data = await absorb(ctx, data, ctx.text)
        answered = (data.amount, data.term_months, data.product_type) != before
    if data.product_type is None:
        return await ask_product(ctx, data)
    if data.product_type is CreditProductType.MORTGAGE:
        return await detail(ctx, data, data.product_type)
    product = await product_of(ctx, data.product_type)
    decision = evaluate(ctx, credit=facts(product, data.product_type.value.upper()))
    stop = blocking_step(ctx, decision, state=COLLECT)
    if stop is not None or product is None:
        return stop or await ask_product(ctx, data.evolve(product_type=None))
    if data.currency is not None and data.currency is not product.currency:
        data = data.evolve(amount=None, currency=None)
    missing = _missing_template(data, product.product_type)
    if missing is not None:
        if ctx.reprompt:
            return _ask(ctx, data, missing, unanswered=False)
        stop = exhausted(ctx, data)
        return stop or _ask(ctx, data, missing, unanswered=data.asked_facts and not answered)
    save(
        ctx,
        data.evolve(
            product_code=product.product_code,
            currency=product.currency,
            purpose=data.purpose if data.purpose and product.allows_purpose(data.purpose) else DEFAULT_PURPOSE,
            asked_facts=False,
            assessment=None,
            explained=False,
        ),
    )
    return Step("ESTIMATE_RISK")
