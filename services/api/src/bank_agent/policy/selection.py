"""Which clauses give a rule its parameters and citations, for a jurisdiction (and, for ELG, a product type).

A rule's parameters are the merged parameters of every current clause of the jurisdiction (or ``ALL``) whose
``bound_rules`` names it, and its clause references are those clauses. The same function serves the loader's
checks and the evaluator, so what is validated is what runs.
"""

from collections.abc import Iterable

from bank_agent.domain.decision import ClauseRef, ParamValue
from bank_agent.domain.locale import Country
from bank_agent.domain.policy import ClauseFamily, Jurisdiction, PolicyClause

PRODUCT_TYPE_PARAM = "product_type"


class ParamConflictError(ValueError):
    """Two clauses bound to the same rule give one parameter different values."""


def _in_jurisdiction(clause: PolicyClause, jurisdiction: Country) -> bool:
    return clause.metadata.jurisdiction in (Jurisdiction(jurisdiction.value), Jurisdiction.ALL)


def rule_clauses(clauses: Iterable[PolicyClause], rule_id: str, jurisdiction: Country) -> tuple[PolicyClause, ...]:
    """Clauses of ``jurisdiction`` or ``ALL`` that bind ``rule_id``, ordered by clause id."""
    selected = [c for c in clauses if rule_id in c.metadata.bound_rules and _in_jurisdiction(c, jurisdiction)]
    return tuple(sorted(selected, key=lambda clause: clause.metadata.clause_id))


def eligibility_clauses(
    clauses: Iterable[PolicyClause], jurisdiction: Country, product_type: str
) -> tuple[PolicyClause, ...]:
    """The ``ELG-ALL-*`` clauses plus the jurisdiction's ELG clauses for ``product_type``, ordered by id."""
    selected = []
    for clause in clauses:
        meta = clause.metadata
        if meta.family is not ClauseFamily.ELG or not _in_jurisdiction(clause, jurisdiction):
            continue
        declared = meta.params.get(PRODUCT_TYPE_PARAM)
        if (meta.jurisdiction is Jurisdiction.ALL and declared is None) or declared == product_type:
            selected.append(clause)
    return tuple(sorted(selected, key=lambda clause: clause.metadata.clause_id))


def merge_params(clauses: Iterable[PolicyClause]) -> dict[str, ParamValue]:
    """Merged parameters; raises ``ParamConflictError`` when two clauses disagree on one name."""
    merged: dict[str, ParamValue] = {}
    for clause in clauses:
        for name, value in clause.metadata.params.items():
            if name in merged and merged[name] != value:
                raise ParamConflictError(f"parameter {name} differs between clauses bound to one rule")
            merged[name] = value
    return merged


def refs(clauses: Iterable[PolicyClause]) -> tuple[ClauseRef, ...]:
    return tuple(clause.ref for clause in clauses)
