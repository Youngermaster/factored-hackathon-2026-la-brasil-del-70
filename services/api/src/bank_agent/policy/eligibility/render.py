"""Turn an ``EligibilityView`` into customer-facing text in es, pt, or en, from the pack's messages and clauses.

The text states that the service is synthetic, the outcome in plain words, each reason once with the clauses
that cite it, any missing information, the uncertainty statement, the review path, and the ``CRE-ALL-1``
disclaimer. No language model is involved, and the text is refused if it contains approval wording.
"""

from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.eligibility import EligibilityView
from bank_agent.domain.errors import PolicyPackInvalidError
from bank_agent.domain.locale import Language, Locale
from bank_agent.policy.explain import RenderedExplanation, render_body
from bank_agent.policy.lexicon import approval_terms
from bank_agent.policy.pack import PolicyPack

DISCLAIMER_CLAUSE = "CRE-ALL-1"


def render_eligibility(
    pack: PolicyPack, view: EligibilityView, language: Language, locale: Locale
) -> RenderedExplanation:
    def message(group: str, key: str) -> str:
        return pack.message(language, group, key)

    lines = [message("heading", "synthetic_notice"), message("outcome", view.outcome.value)]
    citations: list[ClauseRef] = []
    if view.reasons:
        lines.append(message("heading", "reasons"))
        grouped: dict[str, list[ClauseRef]] = {}
        for reason in view.reasons:
            grouped.setdefault(reason.reason_code, []).append(reason.clause)
            citations.append(reason.clause)
        for code, clauses in grouped.items():
            cited = ", ".join(str(clause) for clause in dict.fromkeys(clauses))
            lines.append(f"- {message('reason', code)} ({cited})")
    if view.missing_facts:
        lines.append(message("heading", "missing"))
        lines.extend(f"- {message('missing_fact', fact)}" for fact in view.missing_facts)
    lines.append(message("uncertainty", view.uncertainty.value))
    lines.append(message("review_path", view.review_path.value))
    disclaimer = pack.get_clause(DISCLAIMER_CLAUSE, language)
    lines.append(render_body(disclaimer, locale))
    citations.append(disclaimer.ref)
    text = "\n".join(lines)
    if approval_terms(text):
        raise PolicyPackInvalidError("rendered credit text contains approval wording")
    return RenderedExplanation(language=language, text=text, citations=tuple(dict.fromkeys(citations)))
