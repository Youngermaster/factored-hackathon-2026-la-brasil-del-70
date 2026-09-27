"""ELG rules: the synthetic eligibility rules. They run only inside the synthetic eligibility service.

Parameters come from the ``ELG-ALL-*`` clauses plus the one ``ELG-<country>-*`` clause for the product's
jurisdiction and type. The risk estimate is an input fact (band and interval); nothing here computes it.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext

from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.decision import DecisionKind, ParamValue
from bank_agent.domain.eligibility import RiskBand, RiskEstimate
from bank_agent.domain.money import Money
from bank_agent.policy.rules.registry import RuleRegistry, Verdict, fail, ok, str_list, typed_param
from bank_agent.ports.eligibility import EligibilityRequest

BASIS_POINTS = Decimal(10000)


@dataclass(frozen=True)
class EligibilityContext:
    request: EligibilityRequest
    params: Mapping[str, ParamValue]

    def income(self) -> Money | None:
        """The profile's estimated income, else the income the customer declared in this conversation."""
        profile = self.request.profile
        if profile is not None and profile.estimated_monthly_income is not None:
            return profile.estimated_monthly_income
        return self.request.application.declared_monthly_income

    def estimate(self) -> RiskEstimate | None:
        estimate = self.request.risk_estimate
        return None if estimate is None or estimate.band is RiskBand.UNKNOWN else estimate


ELIGIBILITY_RULES: RuleRegistry[EligibilityContext] = RuleRegistry(prefixes=("ELG.",))
RULES = ELIGIBILITY_RULES
_UNAVAILABLE = fail(DecisionKind.ESCALATE, "risk_estimate_unavailable")


@RULES.rule(
    "ELG.self_service_product",
    version=1,
    reasons=("self_service_product", "product_requires_human_assessment"),
)
def self_service_product(context: EligibilityContext) -> Verdict:
    if context.request.product.self_service_eligibility:
        return ok("self_service_product")
    return fail(DecisionKind.ESCALATE, "product_requires_human_assessment")


def _score(context: EligibilityContext) -> int | None:
    profile = context.request.profile
    return profile.credit_score if profile is not None else None


_NO_SCORE = fail(DecisionKind.CLARIFY, "missing_credit_score", missing=("credit_score",))


@RULES.rule(
    "ELG.credit_score_present",
    version=1,
    reasons=("credit_score_present", "missing_credit_score"),
    missing_facts=("credit_score",),
)
def credit_score_present(context: EligibilityContext) -> Verdict:
    return _NO_SCORE if _score(context) is None else ok("credit_score_present")


@RULES.rule(
    "ELG.credit_score_minimum",
    version=1,
    params={"min_credit_score": int},
    reasons=("credit_score_meets_minimum", "missing_credit_score", "credit_score_below_minimum"),
    missing_facts=("credit_score",),
)
def credit_score_minimum(context: EligibilityContext) -> Verdict:
    minimum = typed_param(context.params, "min_credit_score", int)
    score = _score(context)
    if score is None:
        return _NO_SCORE
    if score < minimum:
        return fail(DecisionKind.DENY, "credit_score_below_minimum", min_credit_score=minimum)
    return ok("credit_score_meets_minimum", min_credit_score=minimum)


_NO_INCOME = fail(DecisionKind.CLARIFY, "missing_income", missing=("monthly_income",))


@RULES.rule(
    "ELG.income_present",
    version=1,
    reasons=("income_present", "missing_income", "income_currency_mismatch"),
    missing_facts=("monthly_income",),
)
def income_present(context: EligibilityContext) -> Verdict:
    income = context.income()
    if income is None:
        return _NO_INCOME
    if income.currency is not context.request.product.currency:
        return fail(DecisionKind.CLARIFY, "income_currency_mismatch", missing=("monthly_income",))
    return ok("income_present")


def monthly_payment(context: EligibilityContext) -> Decimal:
    """A card: a clause percentage of the requested limit. A loan: the annuity at the product's maximum rate."""
    request, product = context.request, context.request.product
    amount = request.application.requested_amount.amount
    with localcontext() as decimal_context:
        decimal_context.prec = 28
        if product.product_type is CreditProductType.CREDIT_CARD:
            return amount * typed_param(context.params, "card_payment_pct_of_limit", int) / 100
        rate = product.max_annual_rate / 100 / 12
        term = request.application.requested_term_months
        if rate == 0:
            return amount / term
        return amount * rate / (1 - (1 + rate) ** -term)


@RULES.rule(
    "ELG.payment_to_income_max",
    version=1,
    params={"max_payment_to_income_pct": int},
    reasons=("payment_to_income_within_maximum", "missing_income", "payment_to_income_above_maximum"),
    missing_facts=("monthly_income",),
)
def payment_to_income_max(context: EligibilityContext) -> Verdict:
    maximum = typed_param(context.params, "max_payment_to_income_pct", int)
    income = context.income()
    if income is None or income.currency is not context.request.product.currency:
        return _NO_INCOME
    payment = monthly_payment(context)
    if income.amount <= 0 or payment * 100 > income.amount * maximum:
        return fail(DecisionKind.DENY, "payment_to_income_above_maximum", max_payment_to_income_pct=maximum)
    return ok("payment_to_income_within_maximum", max_payment_to_income_pct=maximum)


@RULES.rule(
    "ELG.days_past_due_max",
    version=1,
    params={"max_days_past_due": int},
    reasons=("days_past_due_within_maximum", "missing_days_past_due", "days_past_due_present"),
    missing_facts=("max_days_past_due",),
)
def days_past_due_max(context: EligibilityContext) -> Verdict:
    maximum = typed_param(context.params, "max_days_past_due", int)
    profile = context.request.profile
    days = profile.max_days_past_due if profile is not None else None
    if days is None:
        return fail(DecisionKind.CLARIFY, "missing_days_past_due", missing=("max_days_past_due",))
    if days > maximum:
        return fail(DecisionKind.ESCALATE, "days_past_due_present", max_days_past_due=maximum)
    return ok("days_past_due_within_maximum", max_days_past_due=maximum)


@RULES.rule(
    "ELG.tenure_minimum",
    version=1,
    params={"min_tenure_months": int},
    reasons=("tenure_meets_minimum", "missing_tenure", "tenure_below_minimum"),
    missing_facts=("tenure_months",),
)
def tenure_minimum(context: EligibilityContext) -> Verdict:
    minimum = typed_param(context.params, "min_tenure_months", int)
    profile = context.request.profile
    tenure = profile.tenure_months if profile is not None else None
    if tenure is None:
        return fail(DecisionKind.CLARIFY, "missing_tenure", missing=("tenure_months",))
    if tenure < minimum:
        return fail(DecisionKind.DENY, "tenure_below_minimum", min_tenure_months=minimum)
    return ok("tenure_meets_minimum", min_tenure_months=minimum)


@RULES.rule(
    "ELG.amount_within_product_range",
    version=1,
    params={"review_amount_threshold": Money},
    reasons=(
        "amount_within_product_range",
        "amount_outside_product_range",
        "term_outside_product_range",
        "purpose_not_offered",
        "amount_above_review_threshold",
    ),
)
def amount_within_product_range(context: EligibilityContext) -> Verdict:
    """Bounds are inclusive. Above the review threshold but inside the range, a human reviews."""
    threshold = typed_param(context.params, "review_amount_threshold", Money)
    product, application = context.request.product, context.request.application
    amount = application.requested_amount
    if not product.min_amount <= amount <= product.max_amount:
        return fail(DecisionKind.DENY, "amount_outside_product_range")
    if not product.min_term_months <= application.requested_term_months <= product.max_term_months:
        return fail(DecisionKind.DENY, "term_outside_product_range")
    if not product.allows_purpose(application.purpose):
        return fail(DecisionKind.DENY, "purpose_not_offered")
    if threshold.currency is amount.currency and amount > threshold:
        return fail(DecisionKind.ESCALATE, "amount_above_review_threshold", review_amount_threshold=threshold)
    return ok("amount_within_product_range", review_amount_threshold=threshold)


@RULES.rule(
    "ELG.risk_estimate_available",
    version=1,
    reasons=("risk_estimate_available", "risk_estimate_unavailable"),
)
def risk_estimate_available(context: EligibilityContext) -> Verdict:
    return _UNAVAILABLE if context.estimate() is None else ok("risk_estimate_available")


@RULES.rule(
    "ELG.risk_band_acceptable",
    version=1,
    params={"acceptable_risk_bands": list},
    reasons=("risk_band_acceptable", "risk_estimate_unavailable", "risk_band_not_acceptable"),
)
def risk_band_acceptable(context: EligibilityContext) -> Verdict:
    estimate = context.estimate()
    if estimate is None:
        return _UNAVAILABLE
    if estimate.band.value in str_list(context.params, "acceptable_risk_bands"):
        return ok("risk_band_acceptable")
    return fail(DecisionKind.DENY, "risk_band_not_acceptable")


@RULES.rule(
    "ELG.risk_interval_not_borderline",
    version=1,
    params={"risk_cut_medium_bps": int, "risk_cut_high_bps": int, "borderline_margin_bps": int},
    reasons=("risk_interval_clear", "risk_estimate_unavailable", "borderline_risk_interval"),
)
def risk_interval_not_borderline(context: EligibilityContext) -> Verdict:
    """Borderline when the interval, widened by the margin, reaches a band cut point."""
    estimate = context.estimate()
    if estimate is None:
        return _UNAVAILABLE
    margin = Decimal(typed_param(context.params, "borderline_margin_bps", int)) / BASIS_POINTS
    for name in ("risk_cut_medium_bps", "risk_cut_high_bps"):
        cut = Decimal(typed_param(context.params, name, int)) / BASIS_POINTS
        if estimate.interval_low < cut + margin and estimate.interval_high > cut - margin:
            return fail(DecisionKind.ESCALATE, "borderline_risk_interval")
    return ok("risk_interval_clear")
