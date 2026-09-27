"""Closed lexicons, in es, pt, and en, for the claims the grounding verifier checks.

Patterns run on folded text (``numbers.fold_same_length``: lower case, no accents, same positions). They are
deliberately narrow: an affirmative past-tense action ("bloqueamos tu tarjeta", "a contestacao foi registrada"),
a balance or total statement, an eligibility outcome in the pack's own phrasing and its common variants, and the
words that introduce a credit score, income, or risk probability. A paraphrase outside these lists is not
detected; that limit is documented, and the workflow falls back to templates on any violation.
"""

import re
from enum import StrEnum

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.eligibility import EligibilityOutcome


class ClaimedAction(StrEnum):
    """An action a draft says was done. ``unsupported`` covers actions no tool performs (unblock, refund)."""

    BLOCK_CARD = ActionKind.BLOCK_CARD.value
    CREATE_DISPUTE_CASE = ActionKind.CREATE_DISPUTE_CASE.value
    SUBMIT_CREDIT_APPLICATION = ActionKind.SUBMIT_CREDIT_APPLICATION.value
    UNSUPPORTED = "unsupported"


def _compile(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{pattern})" for pattern in patterns))


ACTION_CLAIMS: dict[ClaimedAction, re.Pattern[str]] = {
    ClaimedAction.BLOCK_CARD: _compile(
        r"\b(?:bloqueamos|hemos bloqueado|he bloqueado|bloqueei)\b",
        r"\b(?:quedo|fue|ha sido|ha quedado|foi|ficou) bloquead[ao]s?\b",
        r"\b(?:we|i) (?:have )?blocked\b",
        r"\b(?:has been|was|is now) blocked\b",
    ),
    ClaimedAction.CREATE_DISPUTE_CASE: _compile(
        r"\b(?:registramos|hemos registrado|abrimos|hemos abierto|creamos|hemos creado|criamos)"
        r" (?:tu |su |sua |la |el |una |un |a |o |uma |um )?"
        r"(?:reclamacion|aclaracion|desconocimiento|disputa|caso|contestacao|reclamacao)\b",
        r"\b(?:reclamacion|aclaracion|desconocimiento|disputa|caso|contestacao|reclamacao)"
        r" (?:quedo|fue|ha sido|ha quedado|foi|ficou) (?:registrad|abiert|abert|cread|criad)[ao]\b",
        r"\b(?:we|i) (?:have )?(?:opened|registered|created|filed) (?:your |a |the )?(?:dispute|case|claim)\b",
        r"\b(?:dispute|case|claim) (?:has been|was) (?:opened|registered|created|filed)\b",
    ),
    ClaimedAction.SUBMIT_CREDIT_APPLICATION: _compile(
        r"\b(?:registramos|hemos registrado|enviamos|hemos enviado) (?:tu |su |sua |la |una |a |uma )?"
        r"(?:solicitud|solicitacao)\b",
        r"\b(?:solicitud|solicitacao) (?:quedo|fue|ha sido|ha quedado|foi|ficou) registrada\b",
        r"\b(?:we|i) (?:have )?(?:recorded|submitted|registered) (?:your |the |an? )?application\b",
        r"\bapplication (?:has been|was) (?:recorded|submitted|registered)\b",
    ),
    ClaimedAction.UNSUPPORTED: _compile(
        r"\b(?:desbloqueamos|hemos desbloqueado|reembolsamos|hemos reembolsado|estornamos|desembolsamos)\b",
        r"\b(?:hemos abonado|abonamos el|emitimos una (?:nueva )?tarjeta|emitimos um novo cartao)\b",
        r"\b(?:we|i) (?:have )?(?:unblocked|refunded|disbursed|issued a new card)\b",
    ),
}

BALANCE_TERMS = re.compile(
    r"\b(?:saldo|balance|credito disponible|credito disponivel|limite disponivel|available credit)\b"
)
TOTAL_TERMS = re.compile(r"\b(?:total|totales|totais|suman|somam|totalizan|totalizam|add up to)\b")
INTERNAL_TERMS = re.compile(
    r"\b(?:puntaje|score|pontuacao|probabilidad|probabilidade|probability|ingresos?|renda|income|salario)\b"
)

ELIGIBILITY_CLAIMS: dict[EligibilityOutcome, re.Pattern[str]] = {
    EligibilityOutcome.NOT_ELIGIBLE: _compile(
        r"\bno cumple",
        r"\bno (?:eres|es|serias|seria|resultas|resulta) elegible",
        r"\bno elegible",
        r"\bnao atende",
        r"\bnao (?:e|seria|esta) elegivel",
        r"\bnao elegivel|\binelegivel",
        r"\bdoes not meet|\bdo not meet|\bnot eligible|\bineligible",
    ),
    EligibilityOutcome.INDICATIVELY_ELIGIBLE: _compile(
        r"\bcumples? de forma indicativa",
        r"\b(?:eres|es|serias|seria|resultas|resulta) (?:indicativamente )?elegible",
        r"\bindicativamente elegib|\belegible de forma indicativa",
        r"\batende de forma indicativa",
        r"\b(?:e|seria|esta) (?:indicativamente )?elegivel",
        r"\bindicativamente elegiv|\belegivel de forma indicativa",
        r"\bindicatively meets|\b(?:are|is|would be) (?:indicatively )?eligible",
    ),
    EligibilityOutcome.REVIEW_REQUIRED: _compile(
        r"\bnecesita (?:la |una )?revision",
        r"\brequiere (?:la |una )?revision",
        r"\bprecisa (?:da |de uma )?(?:analise|revisao)",
        r"\brequer (?:a |uma )?(?:analise|revisao)",
        r"\bneeds a review|\brequires (?:a |human )?review",
    ),
    EligibilityOutcome.INSUFFICIENT_DATA: _compile(
        r"\bnos falta informacion|\bfaltan? (?:informacion|datos)|\binformacion insuficiente",
        r"\bfaltam? (?:informacoes|informacao|dados)|\bdados insuficientes",
        r"\bmissing information|\binsufficient (?:data|information)",
    ),
}

_SENTENCE_BREAK = re.compile(r"[.:](?=\s|$)|[!?;]|\n")


def sentences(text: str) -> list[tuple[int, int]]:
    """Sentence spans; a period or colon ends a sentence only before a space or the end, so ``1.250,00`` and
    ``10:30`` never split one."""
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _SENTENCE_BREAK.finditer(text):
        if match.start() > start:
            spans.append((start, match.start()))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def claimed_actions(folded: str) -> list[tuple[ClaimedAction, int, int]]:
    return [
        (action, match.start(), match.end())
        for action, pattern in ACTION_CLAIMS.items()
        for match in pattern.finditer(folded)
    ]


def claimed_outcomes(folded: str) -> list[tuple[EligibilityOutcome, int, int]]:
    """Eligibility outcomes stated in the text; a positive claim inside a negated one does not count."""
    found = [
        (outcome, match.start(), match.end())
        for outcome, pattern in ELIGIBILITY_CLAIMS.items()
        for match in pattern.finditer(folded)
    ]
    negated = [(start, end) for outcome, start, end in found if outcome is EligibilityOutcome.NOT_ELIGIBLE]
    return [
        (outcome, start, end)
        for outcome, start, end in found
        if outcome is not EligibilityOutcome.INDICATIVELY_ELIGIBLE
        or not any(n_start <= start < n_end or start <= n_start < end for n_start, n_end in negated)
    ]
