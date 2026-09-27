"""Cross-checks between clauses, the rule registries, and the eligibility messages.

Every rule a clause binds must be registered; every registered rule must be bound in every jurisdiction with all
the parameters it reads, typed as it expects and without conflicting values; every self-service product type
needs exactly one ELG clause per jurisdiction; and the messages must cover every ELG reason and missing fact.
"""

from collections.abc import Mapping

from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.decision import ParamValue
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.money import Money
from bank_agent.domain.policy import ClauseFamily, Jurisdiction, PolicyClause
from bank_agent.policy.loader.clauses import ClauseIndex
from bank_agent.policy.loader.documents import PackProblems
from bank_agent.policy.rules import CONVERSATION_RULES, ELIGIBILITY_RULES
from bank_agent.policy.rules.registry import ParamType
from bank_agent.policy.selection import (
    PRODUCT_TYPE_PARAM,
    ParamConflictError,
    eligibility_clauses,
    merge_params,
    rule_clauses,
)

SELF_SERVICE_TYPES = (CreditProductType.CREDIT_CARD, CreditProductType.PERSONAL_LOAN)
CARD_ONLY_PARAMS: dict[str, ParamType] = {"card_payment_pct_of_limit": int}


def _typed(value: ParamValue | None, kind: ParamType) -> bool:
    if kind is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, kind)


def _check_params(
    where: str, params: Mapping[str, ParamValue], wanted: Mapping[str, ParamType], problems: PackProblems
) -> None:
    for name, kind in wanted.items():
        if not _typed(params.get(name), kind):
            problems.add(where, f"needs parameter {name} of type {kind.__name__}")


def _merged(where: str, clauses: tuple[PolicyClause, ...], problems: PackProblems) -> dict[str, ParamValue]:
    try:
        return merge_params(clauses)
    except ParamConflictError as error:
        problems.add(where, str(error))
        return {}


def _check_conversation_rules(current: list[PolicyClause], problems: PackProblems) -> None:
    for spec in CONVERSATION_RULES.specs():
        for country in Country:
            bound = rule_clauses(current, spec.rule_id, country)
            where = f"{spec.rule_id} ({country.value})"
            if not bound:
                problems.add(where, "no clause binds the rule")
                continue
            _check_params(where, _merged(where, bound, problems), spec.params, problems)


def _check_eligibility_rules(current: list[PolicyClause], problems: PackProblems) -> None:
    for country in Country:
        for product_type in SELF_SERVICE_TYPES:
            where = f"ELG {country.value} {product_type.value}"
            clauses = eligibility_clauses(current, country, product_type.value)
            specific = [c for c in clauses if c.metadata.jurisdiction is not Jurisdiction.ALL]
            if len(specific) != 1:
                problems.add(where, "needs exactly one ELG clause of the jurisdiction for the product type")
                continue
            params = _merged(where, clauses, problems)
            for spec in ELIGIBILITY_RULES.specs():
                if not any(spec.rule_id in clause.metadata.bound_rules for clause in clauses):
                    problems.add(where, f"no clause binds {spec.rule_id}")
                _check_params(where, params, spec.params, problems)
            if product_type is CreditProductType.CREDIT_CARD:
                _check_params(where, params, CARD_ONLY_PARAMS, problems)
            threshold = params.get("review_amount_threshold")
            if isinstance(threshold, Money) and threshold.currency is not country.default_currency:
                problems.add(where, "the review amount threshold must be in the jurisdiction's currency")


def _check_messages(messages: Mapping[Language, Mapping[str, Mapping[str, str]]], problems: PackProblems) -> None:
    reasons = {code for spec in ELIGIBILITY_RULES.specs() for code in spec.reason_codes}
    facts = {fact for spec in ELIGIBILITY_RULES.specs() for fact in spec.missing_facts}
    for language, groups in messages.items():
        path = f"messages/eligibility.{language.value}.yaml"
        for group, needed in (("reason", reasons), ("missing_fact", facts)):
            missing = sorted(needed - set(groups.get(group, {})))
            if missing:
                problems.add(path, f"group {group} lacks {', '.join(missing)}")


def check_rule_parameters(
    clauses: ClauseIndex, messages: Mapping[Language, Mapping[str, Mapping[str, str]]], problems: PackProblems
) -> None:
    current = [versions[-1] for (_, language), versions in clauses.items() if language is Language.ES and versions]
    for clause in current:
        for rule_id in clause.metadata.bound_rules:
            if rule_id not in CONVERSATION_RULES and rule_id not in ELIGIBILITY_RULES:
                problems.add(clause.metadata.clause_id, f"binds unregistered rule {rule_id}")
        if clause.metadata.family is not ClauseFamily.ELG and PRODUCT_TYPE_PARAM in clause.metadata.params:
            problems.add(clause.metadata.clause_id, "only ELG clauses declare a product type")
    _check_conversation_rules(current, problems)
    _check_eligibility_rules(current, problems)
    _check_messages(messages, problems)
