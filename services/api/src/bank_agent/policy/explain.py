"""Customer-facing explanations built from clause bodies and parameters. No language model is involved.

A placeholder ``{name}`` is replaced by the clause's own parameter, formatted for the customer's locale
(amounts with the locale's separators and the ISO currency code). The loader guarantees every placeholder
names a renderable parameter, so rendering cannot leave one unresolved.
"""

import re
from collections.abc import Iterable, Sequence
from decimal import Decimal

from bank_agent.domain.base import DomainModel
from bank_agent.domain.decision import ClauseRef, Decision, ordered_clause_union
from bank_agent.domain.errors import PolicyPackInvalidError
from bank_agent.domain.locale import Language, Locale
from bank_agent.domain.money import Money
from bank_agent.domain.policy import PolicyClause
from bank_agent.policy.loader.documents import PLACEHOLDER
from bank_agent.policy.pack import PolicyPack

WORKFLOW_FAMILIES = ("ACC", "CRD", "DSP", "CRE", "INF")
_SEPARATORS = {  # (thousands, decimal)
    Locale.ES_MX: (",", "."),
    Locale.EN_US: (",", "."),
    Locale.ES_CO: (".", ","),
    Locale.ES_AR: (".", ","),
    Locale.PT_BR: (".", ","),
}


class RenderedExplanation(DomainModel):
    language: Language
    text: str
    citations: tuple[ClauseRef, ...]


def format_number(value: Decimal, locale: Locale, decimals: int) -> str:
    thousands, decimal_mark = _SEPARATORS[locale]
    quantized = value.quantize(Decimal(1).scaleb(-decimals)) if decimals else value.quantize(Decimal(1))
    sign = "-" if quantized < 0 else ""
    whole, _, fraction = f"{abs(quantized):f}".partition(".")
    groups: list[str] = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    text = thousands.join(groups)
    return f"{sign}{text}{decimal_mark}{fraction}" if fraction else f"{sign}{text}"


def format_money(money: Money, locale: Locale) -> str:
    return f"{format_number(money.amount, locale, money.currency.minor_units)} {money.currency.value}"


def render_body(clause: PolicyClause, locale: Locale) -> str:
    params = clause.metadata.params

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        value = params.get(name)
        if isinstance(value, Money):
            return format_money(value, locale)
        if isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool)):
            return str(value)
        raise PolicyPackInvalidError(f"placeholder {name} of {clause.metadata.clause_id} cannot be rendered")

    return PLACEHOLDER.sub(substitute, clause.body)


def explain(pack: PolicyPack, refs: Iterable[ClauseRef], language: Language, locale: Locale) -> RenderedExplanation:
    """Render the clauses ``refs`` names, at their exact versions, in ``language``, in order."""
    citations = tuple(dict.fromkeys(refs))
    paragraphs = [render_body(pack.get_clause(ref.clause_id, language, ref.version), locale) for ref in citations]
    return RenderedExplanation(language=language, text="\n\n".join(paragraphs), citations=citations)


def decision_refs(decision: Decision) -> Sequence[ClauseRef]:
    """The clauses that explain a decision: the decisive rules' clauses, or, when no rule was decisive (allow or
    require confirmation), the workflow clauses of the rules that ran."""
    if decision.decisive_rule_ids:
        decisive = tuple(r for r in decision.rule_results if r.rule_id in decision.decisive_rule_ids)
        return ordered_clause_union(decisive)
    return tuple(ref for ref in decision.clause_refs if ref.family in WORKFLOW_FAMILIES)


def explain_decision(pack: PolicyPack, decision: Decision, language: Language, locale: Locale) -> RenderedExplanation:
    return explain(pack, decision_refs(decision), language, locale)
