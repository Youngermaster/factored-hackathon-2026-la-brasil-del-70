"""CRE rules: credit product information from the synthetic catalog, with the indicative disclaimer."""

from bank_agent.domain.decision import DecisionKind
from bank_agent.policy.rules.context import CONVERSATION_RULES as RULES
from bank_agent.policy.rules.context import RuleContext
from bank_agent.policy.rules.registry import Verdict, fail, ok


@RULES.rule(
    "CRE.product_in_catalog",
    version=1,
    reasons=("product_in_catalog", "product_unknown", "product_not_in_catalog"),
    missing_facts=("credit_product",),
)
def product_in_catalog(context: RuleContext) -> Verdict:
    credit = context.facts.credit
    if credit is None or (credit.product is None and credit.requested_product_code is None):
        return fail(DecisionKind.CLARIFY, "product_unknown", missing=("credit_product",))
    if credit.product is None:
        return fail(DecisionKind.CLARIFY, "product_not_in_catalog")
    return ok("product_in_catalog", product_code=credit.product.product_code)


@RULES.rule(
    "CRE.offered_in_jurisdiction",
    version=1,
    reasons=("offered_in_jurisdiction", "product_unknown", "product_not_offered_in_jurisdiction"),
    missing_facts=("credit_product",),
)
def offered_in_jurisdiction(context: RuleContext) -> Verdict:
    credit = context.facts.credit
    product = credit.product if credit is not None else None
    if product is None:
        return fail(DecisionKind.CLARIFY, "product_unknown", missing=("credit_product",))
    if product.jurisdiction is not context.facts.jurisdiction:
        return fail(DecisionKind.DENY, "product_not_offered_in_jurisdiction", product_code=product.product_code)
    return ok("offered_in_jurisdiction", product_code=product.product_code)


@RULES.rule("CRE.disclaimer_present", version=1, reasons=("disclaimer_present", "disclaimer_missing"))
def disclaimer_present(context: RuleContext) -> Verdict:
    credit = context.facts.credit
    if credit is None or not credit.disclaimer_included:
        return fail(DecisionKind.DENY, "disclaimer_missing")
    return ok("disclaimer_present")
