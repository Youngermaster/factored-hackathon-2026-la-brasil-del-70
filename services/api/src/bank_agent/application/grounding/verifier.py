"""The grounding verifier: deterministic checks on a response draft before any customer sees it.

It returns typed violations and never rewrites the draft; the workflow (phase 09) falls back to a template on any
violation. The checks: citations exist, are current, and belong to the jurisdiction; every figure (amount, date,
duration, percentage, number, masked reference) matches a cited or bound clause parameter, a record fact, or the
catalog entry; currency markers agree with the account currency; action claims have a verified result; balance
and total statements match their facts and balances carry their as-of date; eligibility claims need an assessment
with the same outcome; credit text has no approval wording; and no credit score, income, or risk figure appears.
"""

from decimal import Decimal

from bank_agent.application.grounding.draft import GroundingContext, ResponseDraft, Violation, ViolationKind
from bank_agent.application.grounding.evidence import Evidence, collect_catalog, collect_facts, collect_forbidden
from bank_agent.application.grounding.lexicon import (
    BALANCE_TERMS,
    INTERNAL_TERMS,
    TOTAL_TERMS,
    ClaimedAction,
    claimed_actions,
    claimed_outcomes,
    sentences,
)
from bank_agent.application.grounding.numbers import (
    DurationUnit,
    Figure,
    FigureKind,
    citation_markers,
    extract_figures,
    fold_same_length,
)
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.errors import PolicyClauseNotFoundError
from bank_agent.domain.locale import Locale
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.policy import Jurisdiction, PolicyClause
from bank_agent.policy.explain import render_body
from bank_agent.policy.lexicon import approval_terms
from bank_agent.ports.policy import PolicyRepository

_ISO_CODES = {currency.value for currency in Currency}


class GroundingVerifier:
    def __init__(self, repository: PolicyRepository) -> None:
        self._repository = repository

    def verify(self, draft: ResponseDraft, context: GroundingContext) -> tuple[Violation, ...]:
        violations: list[Violation] = []
        evidence = Evidence()
        clauses = self._clauses(draft, context, violations)
        for clause in clauses:
            for name, value in clause.metadata.params.items():
                evidence.add_param(name, value)
        collect_facts(evidence, context)
        collect_catalog(evidence, context)
        collect_forbidden(evidence, context)
        folded = fold_same_length(draft.text)
        figures = extract_figures(draft.text)
        self._check_figures(figures, folded, context, evidence, violations)
        self._check_balances(figures, folded, evidence, violations)
        quoted = _quoted_spans(folded, clauses)
        _check_actions(folded, context, violations, quoted)
        _check_credit(draft.text, folded, context, violations, quoted)
        return tuple(violations)

    # --- citations -------------------------------------------------------------------------------------------

    def _clause(
        self, clause_id: str, version: int | None, context: GroundingContext, out: list[Violation]
    ) -> PolicyClause | None:
        try:
            current = self._repository.get_clause(clause_id, context.language)
        except PolicyClauseNotFoundError:
            out.append(
                Violation(kind=ViolationKind.UNKNOWN_CLAUSE, detail="cited clause does not exist", clause_id=clause_id)
            )
            return None
        if version is not None and version != current.metadata.version:
            detail = "cited clause version is not the current version"
            out.append(Violation(kind=ViolationKind.STALE_CLAUSE_VERSION, detail=detail, clause_id=clause_id))
            return None
        if current.metadata.jurisdiction not in {Jurisdiction(context.jurisdiction.value), Jurisdiction.ALL}:
            detail = "cited clause belongs to another jurisdiction"
            out.append(Violation(kind=ViolationKind.CLAUSE_OUTSIDE_JURISDICTION, detail=detail, clause_id=clause_id))
            return None
        return current

    def _clauses(self, draft: ResponseDraft, context: GroundingContext, out: list[Violation]) -> list[PolicyClause]:
        cited: dict[tuple[str, int | None], None] = {(ref.clause_id, ref.version): None for ref in draft.citations}
        for marker in citation_markers(draft.text):
            clause_id, _, version = marker.partition("@")
            cited.setdefault((clause_id, int(version) if version else None), None)
        clauses = [self._clause(clause_id, version, context, out) for clause_id, version in cited]
        for ref in context.bound_clauses:
            clauses.append(self._bound(ref, context))
        return [clause for clause in clauses if clause is not None]

    def _bound(self, ref: ClauseRef, context: GroundingContext) -> PolicyClause | None:
        try:
            return self._repository.get_clause(ref.clause_id, context.language, ref.version)
        except PolicyClauseNotFoundError:
            return None

    # --- figures ---------------------------------------------------------------------------------------------

    def _check_figures(
        self,
        figures: tuple[Figure, ...],
        folded: str,
        context: GroundingContext,
        evidence: Evidence,
        out: list[Violation],
    ) -> None:
        spans = sentences(folded)
        for figure in figures:
            sentence = next((folded[a:b] for a, b in spans if a <= figure.start < b), "")
            clause_value = any(value in evidence.clause_numbers for value in figure.values)
            if any(value in evidence.forbidden for value in figure.values) and not clause_value:
                out.append(_violation(ViolationKind.INTERNAL_FIGURE_DISCLOSED, "an internal credit figure", figure))
                continue
            if figure.values and INTERNAL_TERMS.search(sentence) and not clause_value:
                detail = "a figure next to a credit score, income, or risk term"
                out.append(_violation(ViolationKind.INTERNAL_FIGURE_DISCLOSED, detail, figure))
                continue
            violation = self._check_figure(figure, sentence, context, evidence)
            if violation is not None:
                out.append(violation)

    def _check_figure(
        self, figure: Figure, sentence: str, context: GroundingContext, evidence: Evidence
    ) -> Violation | None:
        values = set(figure.values)
        if figure.kind is FigureKind.REFERENCE:
            ok = figure.digits in evidence.references
            return None if ok else _violation(ViolationKind.UNSUPPORTED_REFERENCE, "a masked number", figure)
        if figure.kind in (FigureKind.DATE, FigureKind.TIME):
            ok = (
                (figure.day is not None and figure.day in evidence.dates)
                or (figure.month_day is not None and figure.month_day in {(d.month, d.day) for d in evidence.dates})
                or (figure.time is not None and figure.time in evidence.times)
            )
            return None if ok else _violation(ViolationKind.UNSUPPORTED_DATE, "a date or time", figure)
        if figure.kind is FigureKind.PERCENT:
            if values & evidence.percents:
                return None
            kind = ViolationKind.RATE_NOT_IN_CATALOG if context.is_credit else ViolationKind.UNSUPPORTED_NUMBER
            return _violation(kind, "a percentage", figure)
        if figure.kind is FigureKind.DURATION:
            if any((value, figure.unit) in evidence.durations for value in values):
                return None
            in_catalog = context.catalog_product is not None and figure.unit is DurationUnit.MONTHS
            kind = ViolationKind.CATALOG_FIGURE_MISMATCH if in_catalog else ViolationKind.UNSUPPORTED_DURATION
            return _violation(kind, "a duration", figure)
        pool, kind = evidence.money, ViolationKind.UNSUPPORTED_AMOUNT
        if BALANCE_TERMS.search(sentence):
            pool, kind = evidence.balance_money, ViolationKind.BALANCE_MISMATCH
        elif TOTAL_TERMS.search(sentence):
            pool, kind = evidence.total_money, ViolationKind.STATEMENT_TOTAL_MISMATCH
        elif context.catalog_product is not None:
            kind = ViolationKind.CATALOG_FIGURE_MISMATCH
        if figure.kind is FigureKind.NUMBER:
            if kind in (ViolationKind.BALANCE_MISMATCH, ViolationKind.STATEMENT_TOTAL_MISMATCH):
                ok = any(money.amount in values for money in pool)
                return None if ok else _violation(kind, "an amount without a currency", figure)
            ok = bool(values & evidence.numbers)
            return None if ok else _violation(ViolationKind.UNSUPPORTED_NUMBER, "a number", figure)
        return _check_money(figure, values, pool, kind, context, evidence)

    def _check_balances(
        self, figures: tuple[Figure, ...], folded: str, evidence: Evidence, out: list[Violation]
    ) -> None:
        """Every balance statement needs the as-of date of the balance facts somewhere in the draft."""
        amounts = [f for f in figures if f.kind in (FigureKind.MONEY, FigureKind.NUMBER)]
        statements = [
            (a, b)
            for a, b in sentences(folded)
            if BALANCE_TERMS.search(folded[a:b]) and any(a <= f.start < b for f in amounts)
        ]
        if not statements:
            return
        dated = any(
            (f.day is not None and f.day in evidence.as_of_dates)
            or (f.month_day is not None and f.month_day in {(d.month, d.day) for d in evidence.as_of_dates})
            for f in figures
            if f.kind is FigureKind.DATE
        )
        if not dated:
            detail = "a balance statement without the as-of date of its data"
            out.append(Violation(kind=ViolationKind.BALANCE_WITHOUT_AS_OF, detail=detail, span=statements[0]))


def _violation(kind: ViolationKind, what: str, figure: Figure) -> Violation:
    return Violation(
        kind=kind, detail=f"{what} that no clause, record, or catalog entry supports", span=(figure.start, figure.end)
    )


def _check_money(
    figure: Figure,
    values: set[Decimal],
    pool: list[Money],
    kind: ViolationKind,
    context: GroundingContext,
    evidence: Evidence,
) -> Violation | None:
    marker = figure.currency_marker
    if marker in ("$", "PESO"):
        if context.currency is None:
            return Violation(
                kind=ViolationKind.CURRENCY_UNRESOLVED,
                detail="a currency symbol with no account currency to resolve it",
                span=(figure.start, figure.end),
            )
        if marker == "PESO" and context.currency is Currency.USD:
            return _conflict(figure)
        currency: Currency | None = context.currency
    else:
        currency = Currency(marker) if marker in _ISO_CODES else None
    if currency is not None and any(m.currency is currency and m.amount in values for m in pool):
        return None
    if currency is None or any(m.amount in values and m.currency is not currency for m in evidence.money):
        return _conflict(figure)
    if context.currency is not None and currency is not context.currency:
        return _conflict(figure)
    return _violation(kind, "an amount", figure)


def _conflict(figure: Figure) -> Violation:
    return Violation(
        kind=ViolationKind.CURRENCY_CONFLICT,
        detail="a currency that differs from the account currency or from the record",
        span=(figure.start, figure.end),
    )


# --- claims --------------------------------------------------------------------------------------------------


def _quoted_spans(folded: str, clauses: list[PolicyClause]) -> list[tuple[int, int]]:
    """Draft sentences that repeat a whole sentence of a cited or bound clause, as rendered in any locale of its
    language. Quoted policy describes what happens in general; it is not a claim about this conversation."""
    policy: set[str] = set()
    for clause in clauses:
        for locale in Locale:
            if locale.language is clause.metadata.language:
                body = fold_same_length(render_body(clause, locale))
                policy |= {body[a:b].strip() for a, b in sentences(body)}
    return [(a, b) for a, b in sentences(folded) if folded[a:b].strip() in policy]


def _inside(start: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= start < b for a, b in spans)


def _check_actions(folded: str, context: GroundingContext, out: list[Violation], quoted: list[tuple[int, int]]) -> None:
    """An action may be stated as done only when a verified result of that action was passed in."""
    verified = {action.kind for action in context.actions if action.verified}
    for claimed, start, end in claimed_actions(folded):
        if _inside(start, quoted):
            continue
        if claimed is ClaimedAction.UNSUPPORTED:
            detail = "a claim of an action no tool performs"
            out.append(Violation(kind=ViolationKind.UNSUPPORTED_ACTION_CLAIM, detail=detail, span=(start, end)))
            continue
        kind = ActionKind(claimed.value)
        if kind not in verified:
            detail = "a claim of an action without a verified result"
            out.append(
                Violation(kind=ViolationKind.UNVERIFIED_ACTION_CLAIM, detail=detail, span=(start, end), action=kind)
            )


def _check_credit(
    text: str, folded: str, context: GroundingContext, out: list[Violation], quoted: list[tuple[int, int]]
) -> None:
    """Eligibility claims match the assessment; credit text never contains approval wording; the catalog entry
    belongs to the verified jurisdiction."""
    product = context.catalog_product
    if product is not None and product.jurisdiction is not context.jurisdiction:
        detail = "a catalog entry from another jurisdiction"
        out.append(Violation(kind=ViolationKind.CATALOG_JURISDICTION_MISMATCH, detail=detail))
    for outcome, start, end in claimed_outcomes(folded):
        if _inside(start, quoted):
            continue
        if context.eligibility is None:
            detail = "an eligibility statement without an eligibility assessment"
            out.append(Violation(kind=ViolationKind.ELIGIBILITY_WITHOUT_ASSESSMENT, detail=detail, span=(start, end)))
        elif outcome is not context.eligibility.outcome:
            detail = f"states {outcome.value}, but the assessment is {context.eligibility.outcome.value}"
            out.append(Violation(kind=ViolationKind.ELIGIBILITY_OUTCOME_MISMATCH, detail=detail, span=(start, end)))
    if context.is_credit and approval_terms(text):
        detail = "approval wording in a credit response"
        out.append(Violation(kind=ViolationKind.APPROVAL_WORDING, detail=detail))
