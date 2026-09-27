"""The values a draft may state, collected from cited clauses, record facts, and the catalog entry, and the
internal values it must never state."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from bank_agent.application.grounding.draft import BALANCE_FACTS, MONEY_FACTS, FactKind, GroundingContext
from bank_agent.application.grounding.numbers import DurationUnit
from bank_agent.domain.decision import ParamValue
from bank_agent.domain.money import Money

_UNIT_SUFFIXES = (
    ("_business_days", DurationUnit.BUSINESS_DAYS),
    ("_days", DurationUnit.DAYS),
    ("_hours", DurationUnit.HOURS),
    ("_minutes", DurationUnit.MINUTES),
    ("_months", DurationUnit.MONTHS),
    ("_years", DurationUnit.YEARS),
)


def unit_of(param_name: str) -> DurationUnit | None:
    """The duration unit a parameter name declares (``dispute_window_days`` -> days), if any."""
    for suffix, unit in _UNIT_SUFFIXES:
        if param_name.endswith(suffix):
            return unit
    return None


@dataclass
class Evidence:
    money: list[Money] = field(default_factory=list)
    balance_money: list[Money] = field(default_factory=list)
    total_money: list[Money] = field(default_factory=list)
    catalog_money: list[Money] = field(default_factory=list)
    numbers: set[Decimal] = field(default_factory=set)
    clause_numbers: set[Decimal] = field(default_factory=set)
    percents: set[Decimal] = field(default_factory=set)
    catalog_rates: set[Decimal] = field(default_factory=set)
    durations: set[tuple[Decimal, DurationUnit]] = field(default_factory=set)
    dates: set[date] = field(default_factory=set)
    as_of_dates: set[date] = field(default_factory=set)
    times: set[tuple[int, int]] = field(default_factory=set)
    references: set[str] = field(default_factory=set)
    forbidden: set[Decimal] = field(default_factory=set)

    def add_param(self, name: str, value: ParamValue) -> None:
        if isinstance(value, Money):
            self.money.append(value)
            self.clause_numbers.add(value.amount)
            self.numbers.add(value.amount)
        elif isinstance(value, int) and not isinstance(value, bool):
            number = Decimal(value)
            self.numbers.add(number)
            self.clause_numbers.add(number)
            unit = unit_of(name)
            if unit is not None:
                self.durations.add((number, unit))
            if "_pct" in name:
                self.percents.add(number)

    def add_date(self, day: date, *, as_of: bool = False) -> None:
        self.dates.add(day)
        self.numbers.add(Decimal(day.year))
        if as_of:
            self.as_of_dates.add(day)


def collect_facts(evidence: Evidence, context: GroundingContext) -> None:
    for fact in context.facts:
        if fact.kind in MONEY_FACTS and fact.money is not None:
            evidence.money.append(fact.money)
            evidence.numbers.add(fact.money.amount)
            if fact.kind in BALANCE_FACTS:
                evidence.balance_money.append(fact.money)
            if fact.kind is FactKind.STATEMENT_TOTAL:
                evidence.total_money.append(fact.money)
        elif fact.kind is FactKind.AS_OF:
            if fact.at is not None:
                evidence.times.add((fact.at.hour, fact.at.minute))
            if fact.as_of_date is not None:
                evidence.add_date(fact.as_of_date, as_of=True)
        elif fact.kind is FactKind.DATE and fact.day is not None:
            evidence.add_date(fact.day)
        elif fact.number is not None:
            evidence.numbers.add(fact.number)
            if fact.kind is FactKind.DAYS:
                evidence.durations.add((fact.number, DurationUnit.DAYS))
        elif fact.reference is not None:
            evidence.references.add(fact.reference)


def collect_catalog(evidence: Evidence, context: GroundingContext) -> None:
    product = context.catalog_product
    if product is None:
        return
    for money in (product.min_amount, product.max_amount):
        evidence.catalog_money.append(money)
        evidence.money.append(money)
        evidence.numbers.add(money.amount)
    for months in (product.min_term_months, product.max_term_months):
        evidence.durations.add((Decimal(months), DurationUnit.MONTHS))
        evidence.numbers.add(Decimal(months))
    for rate in (product.min_annual_rate, product.max_annual_rate):
        evidence.catalog_rates.add(rate)
        evidence.percents.add(rate)
        evidence.numbers.add(rate)


def _fraction_forms(probability: Decimal) -> set[Decimal]:
    value = Decimal(probability)
    forms = {round(value, places) for places in (2, 3, 4)}
    forms |= {round(value * 100, places) for places in (0, 1, 2)}
    return {form.normalize() for form in forms}


def collect_forbidden(evidence: Evidence, context: GroundingContext) -> None:
    """Credit score, income, and risk estimate figures: never in customer text."""
    profile = context.credit_profile
    if profile is not None:
        if profile.credit_score is not None:
            evidence.forbidden.add(Decimal(profile.credit_score))
        if profile.estimated_monthly_income is not None:
            evidence.forbidden.add(profile.estimated_monthly_income.amount)
    if context.declared_income is not None:
        evidence.forbidden.add(context.declared_income.amount)
    estimate = context.risk_estimate
    if estimate is not None:
        for probability in (estimate.probability, estimate.interval_low, estimate.interval_high):
            evidence.forbidden |= _fraction_forms(probability)
