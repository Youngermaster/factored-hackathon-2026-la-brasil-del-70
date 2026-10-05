"""UNDERSTAND for credit: the router's intent, ``extract_credit_slots`` through the gateway with a deterministic
fallback, and in-domain unsupported requests.

The model sees only the customer's message: never the credit profile, the risk estimate, or the eligibility rules.
It proposes a product, an amount, a term, a purpose, and a declared income; deterministic code normalizes amounts,
terms, and income from the text first and maps the purpose to the catalog's codes.
"""

from decimal import Decimal

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.llm import EXTRACT_CREDIT, structured
from bank_agent.application.engine.shared import abstain_unsupported
from bank_agent.application.understanding import slots
from bank_agent.application.workflows.credit.approval import APPROVAL_QUESTION, asks_approval
from bank_agent.application.workflows.credit.data import CreditData, load, save
from bank_agent.application.workflows.credit.unsupported import recognize
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.llm_outputs import CreditSlotExtraction
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import Intent

CREDIT_INTENTS = frozenset(
    {
        Intent.CREDIT_PRODUCT_INFO,
        Intent.CREDIT_ELIGIBILITY,
        Intent.CREDIT_APPLICATION,
        Intent.CREDIT_APPLICATION_STATUS,
    }
)
ASSESSING = frozenset({Intent.CREDIT_ELIGIBILITY, Intent.CREDIT_APPLICATION})


def _money(amount: Decimal | None, currency: Currency | None) -> Money | None:
    if amount is None or amount <= 0 or currency is None:
        return None
    return Money.of(str(amount), currency)


async def absorb(ctx: TurnContext, data: CreditData, text: str, *, use_model: bool = True) -> CreditData:
    """Merge what ``text`` says into ``data``; the text's own figures win over the model's plain numbers."""
    model: CreditSlotExtraction | None = None
    if use_model:
        variables = {"customer_message": ctx.text, "dialect_hint": ctx.locale.value}
        model = await structured(ctx, EXTRACT_CREDIT, variables, CreditSlotExtraction)
    currency = ctx.customer.country.default_currency
    changes: dict[str, object] = {}
    named = slots.credit_product_types(text)
    product_type = slots.credit_product_type(text)
    if product_type is None and not named and model is not None:
        # The model's product is used only when the text names none; a text naming several asks for the list.
        product_type = model.product_of_interest
    if product_type is not None and product_type is not data.product_type:
        changes["product_type"], changes["product_code"] = product_type, None
    found = slots.credit_amounts(text)
    requested = found.requested.amount if found.requested is not None else None
    if requested is None and model is not None:
        requested = model.requested_amount
    if slots.positive(requested) is not None:
        changes["amount"] = requested
        # A figure the text states without a currency ("50.000 pesos", "50000") is in the customer's own currency;
        # the model's currency is used only for an amount the text parser did not find (phase 14b: the local model
        # said COP for a Mexican customer's "50.000 pesos", and the amount was dropped and asked again).
        explicit = found.requested.currency if found.requested is not None else None
        guessed = model.currency_hint if model is not None and found.requested is None else None
        changes["currency"] = explicit or guessed or currency
    term = slots.term_months(text) or (model.requested_term_months if model is not None else None)
    if term is not None:
        changes["term_months"] = term
    income_amount = found.income.amount if found.income is not None else None
    if income_amount is None and model is not None:
        income_amount = model.declared_monthly_income
    income = _money(income_amount, currency)
    if income is not None:
        changes["declared_income"] = income
    purpose = slots.purpose(text)
    if purpose is not None:
        changes["purpose"] = purpose
    return data.evolve(**changes) if changes else data


async def understand(ctx: TurnContext) -> Step:
    request = recognize(ctx.text)
    if request is not None:
        return abstain_unsupported(ctx, request)
    if asks_approval(ctx.text):
        return abstain_unsupported(ctx, APPROVAL_QUESTION)
    routed = ctx.prediction.intent if ctx.prediction is not None else None
    intent = routed if routed in CREDIT_INTENTS else (ctx.engine.intent or Intent.CREDIT_PRODUCT_INFO)
    if intent not in CREDIT_INTENTS:
        intent = Intent.CREDIT_PRODUCT_INFO
    previous = load(ctx)
    data = await absorb(ctx, CreditData(intent=intent, declared_income=previous.declared_income), ctx.text)
    ctx.engine = ctx.engine.evolve(intent=intent)
    save(ctx, data)
    if intent is Intent.CREDIT_APPLICATION_STATUS:
        return Step("APPLICATION_STATUS")
    if intent in ASSESSING and data.product_type is not CreditProductType.MORTGAGE:
        return Step("COLLECT_APPLICATION_FACTS")
    return Step("PRODUCT_INFO")
