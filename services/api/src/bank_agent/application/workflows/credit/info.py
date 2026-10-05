"""PRODUCT_INFO and CLARIFY for credit: answers from the synthetic catalog, and which product the customer means.

Every answer comes from ``list_credit_products`` or ``get_credit_product`` for the verified customer's country, with
the ``CRE-ALL-1`` disclaimer; figures (amounts, terms, rates) come only from the catalog entry, and the verifier
receives the entry as evidence. No eligibility is claimed here. Mortgages are information only: an eligibility
question about a mortgage is answered from the catalog with ``ELG-ALL-3`` and a person is offered.
"""

from decimal import Decimal

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import evaluate
from bank_agent.application.engine.reply import Choices, CreditEvidence, Param, Reply
from bank_agent.application.engine.shared import blocking_step, clause_ref
from bank_agent.application.engine.templates.labels import CREDIT_TYPES, pick
from bank_agent.application.understanding.answers import parse_choice
from bank_agent.application.understanding.text import fold
from bank_agent.application.workflows.credit.data import CreditData, exhausted, load, save
from bank_agent.application.workflows.credit.understand import ASSESSING, absorb
from bank_agent.domain.credit import CreditProduct, CreditProductType
from bank_agent.domain.locale import Locale
from bank_agent.domain.workflow import Intent, Outcome
from bank_agent.policy.explain import format_number
from bank_agent.policy.facts import CreditFacts

PRODUCT_INFO = "PRODUCT_INFO"
CLARIFY = "CLARIFY"
COLLECT = "COLLECT_APPLICATION_FACTS"


def rate(value: Decimal, locale: Locale) -> str:
    places = 0 if value == value.to_integral_value() else 2
    return f"{format_number(value, locale, places)} %"


def name(ctx: TurnContext, product_type: CreditProductType) -> str:
    return pick(CREDIT_TYPES[product_type], ctx.language)


async def product_of(ctx: TurnContext, product_type: CreditProductType) -> CreditProduct | None:
    """The catalog entry of ``product_type`` in the customer's country (read through the scoped tools)."""
    listed = await ctx.tools.list_credit_products()
    code = next((p.product_code for p in listed if p.product_type is product_type), None)
    return await ctx.tools.get_credit_product(code) if code is not None else None


def facts(product: CreditProduct | None, code: str | None = None) -> CreditFacts:
    return CreditFacts(
        requested_product_code=product.product_code if product is not None else code,
        product=product,
        disclaimer_included=True,
    )


def country_clauses(ctx: TurnContext) -> tuple[str, ...]:
    return (f"CRE-{ctx.customer.country.value}-1", "CRE-ALL-1")


async def _listing(ctx: TurnContext, data: CreditData) -> Step:
    products = list(await ctx.tools.list_credit_products())
    decision = evaluate(ctx, policy_state="LIST_PRODUCTS", credit=facts(None, "catalog"))
    stop = blocking_step(ctx, decision, state=PRODUCT_INFO)
    if stop is not None:
        return stop
    lines: list[tuple[str, dict[str, Param]]] = []
    for product in products:
        template = "credit.product_line" if product.self_service_eligibility else "credit.product_line_info_only"
        lines.append((template, {"name": name(ctx, product.product_type), "min": product.min_amount,
                                 "max": product.max_amount}))  # fmt: skip
    lines.append(("credit.ask_which_product", {}))
    save(ctx, data.evolve(listed=True, detailed=False))
    explain = tuple(clause_ref(ctx, clause_id) for clause_id in country_clauses(ctx))
    reply = Reply(template="credit.product_list", suffix=tuple(lines), explain=explain, credit_products=tuple(products))
    return Step(PRODUCT_INFO, reply, Outcome.RESOLVED)


def detail_reply(ctx: TurnContext, product: CreditProduct, *, closing: str) -> Reply:
    card = product.product_type is CreditProductType.CREDIT_CARD
    params: dict[str, Param] = {
        "name": name(ctx, product.product_type).capitalize(),
        "min": product.min_amount,
        "max": product.max_amount,
        "min_rate": rate(product.min_annual_rate, ctx.locale),
        "max_rate": rate(product.max_annual_rate, ctx.locale),
    }
    if not card:
        params["min_term"], params["max_term"] = product.min_term_months, product.max_term_months
    clauses = ("CRE-ALL-2", *(("ELG-ALL-3",) if closing == "credit.mortgage_info_only" else ()), *country_clauses(ctx))
    return Reply(
        template="credit.product_detail_card" if card else "credit.product_detail",
        params=params,
        suffix=((closing, {}),),
        explain=tuple(clause_ref(ctx, clause_id) for clause_id in clauses),
        credit=CreditEvidence(product=product),
        credit_products=(product,),
    )


async def detail(ctx: TurnContext, data: CreditData, product_type: CreditProductType) -> Step:
    product = await product_of(ctx, product_type)
    decision = evaluate(ctx, policy_state="PRODUCT_DETAIL", credit=facts(product, product_type.value.upper()))
    stop = blocking_step(ctx, decision, state=PRODUCT_INFO)
    if stop is not None or product is None:
        return stop or await _listing(ctx, data)
    info_only = not product.self_service_eligibility
    save(ctx, data.evolve(product_type=product_type, product_code=product.product_code, detailed=True))
    if info_only and data.intent in ASSESSING:
        ctx.recorder.intervention("mortgage_information_only")
        return Step("ABSTAINED", detail_reply(ctx, product, closing="credit.mortgage_info_only"), Outcome.ABSTAINED)
    closing = "credit.mortgage_info_only" if info_only else "credit.offer_guide"
    return Step(PRODUCT_INFO, detail_reply(ctx, product, closing=closing), Outcome.RESOLVED)


async def product_info(ctx: TurnContext) -> Step:
    data = load(ctx)
    if ctx.reprompt:
        return Step(PRODUCT_INFO, Reply(template="credit.anything_else"), Outcome.IN_PROGRESS)
    if data.listed or data.detailed:
        routed = ctx.prediction.intent if ctx.prediction is not None else None
        data = await absorb(ctx, data, ctx.text)
        if routed in ASSESSING and data.product_type is not None:
            save(ctx, data.evolve(intent=routed))
            return Step(COLLECT)
        if data.product_type is None or routed not in (None, Intent.CREDIT_PRODUCT_INFO):
            return Step("UNDERSTAND")
        return await detail(ctx, data, data.product_type)
    if data.product_type is None:
        return await _listing(ctx, data)
    return await detail(ctx, data, data.product_type)


def _options(ctx: TurnContext, *, unanswered: bool = False) -> Step:
    items: tuple[dict[str, Param], ...] = tuple({"name": name(ctx, kind)} for kind in CreditProductType)
    reply = Reply(template="credit.clarify_product", params={"options": Choices("credit.product_option", items)})
    return Step(CLARIFY, reply, Outcome.CLARIFIED, unanswered=unanswered)


async def ask_product(ctx: TurnContext, data: CreditData) -> Step:
    stop = exhausted(ctx, data)
    if stop is not None:
        return stop
    save(ctx, data.evolve(choosing_product=True))
    return _options(ctx)


async def clarify(ctx: TurnContext) -> Step:
    data = load(ctx)
    if ctx.reprompt:
        return _options(ctx)
    kinds = list(CreditProductType)

    def matches(folded: str, kind: CreditProductType) -> bool:
        return any(word in folded for word in fold(name(ctx, kind)).split() if len(word) > 6)

    index = parse_choice(ctx.text, kinds, matches)
    chosen = kinds[index] if index is not None else (await absorb(ctx, data, ctx.text, use_model=False)).product_type
    if chosen is None:
        stop = exhausted(ctx, data)
        return stop or _options(ctx, unanswered=True)
    data = data.evolve(product_type=chosen, product_code=None, choosing_product=False)
    save(ctx, data)
    return Step(COLLECT if data.intent in ASSESSING and chosen is not CreditProductType.MORTGAGE else PRODUCT_INFO)
