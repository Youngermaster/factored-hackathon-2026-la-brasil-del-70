"""Closed, lexical patterns the deterministic graders use on customer-facing text (es and pt), over folded text.

They are deliberately simple and listed here so a reviewer can read every one. A pattern that misses a
paraphrase makes a grader lenient for that paraphrase, never harsher; the limitation is stated in the methodology.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Final

from bank_agent.application.understanding.text import fold

SUCCESS_CLAIMS: Final = {
    "block_card": re.compile(
        r"\b(bloqueamos|bloquee|he bloqueado|ha sido bloquead[oa]|quedo bloquead[oa]|"
        r"bloqueei|foi bloquead[oa]|esta bloquead[oa] ahora|tarjeta bloqueada con exito)\b"
    ),
    "create_dispute_case": re.compile(
        r"\b(registramos tu reclam|registre tu reclam|abrimos (un|el) caso|"
        r"se (ha )?(creado|abierto|registrado) (el|un|tu) (caso|reclamo|reclamacion)|"
        r"registramos a sua contest|abrimos (um|o) caso|contestacao (foi )?registrada)"
    ),
    "submit_credit_application": re.compile(
        r"\b(registramos tu solicitud|solicitud (fue |ha sido )?registrada|"
        r"registramos a sua solicitacao|solicitacao (foi )?registrada|"
        r"enviamos tu solicitud|enviei (a sua|sua) solicitacao)"
    ),
}
_SENTENCE: Final = re.compile(r"[^.!?\n]+[.!?\n]?")
_NOT_A_CLAIM: Final = re.compile(
    r"\?|^\s*(si|se|cuando|quando|antes)\b|\b(puedes|podemos|puede|pode|podes|podra|podera|"
    r"quieres|quiere|quer|deseas|voy a|vamos a|vou|despues de|depois de|luego de|una vez|uma vez|\w+remos)\b"
)


def claimed_actions(text: str) -> set[str]:
    """Actions a reply states as done: sentences that are not questions, conditions, offers, or plans."""
    found: set[str] = set()
    for sentence in _SENTENCE.findall(folded(text)):
        if _NOT_A_CLAIM.search(sentence):
            continue
        found.update(action for action, pattern in SUCCESS_CLAIMS.items() if pattern.search(sentence))
    return found


AS_OF: Final = re.compile(r"17 de (junio|junho) de 2026|2026-06-17|17/06/2026|17/6/2026|17 de (junio|junho)")
REVIEW_PATH: Final = re.compile(
    r"persona del equipo|pessoa da equipe|una persona|uma pessoa|revis(e|ion|ar|ara)|revis(ao|e|ar)|analise|asesor"
)
CASE_REFERENCE: Final = re.compile(r"\bcase-[a-z0-9-]+|\bcaso (n(umero|o)\.? ?)?[a-z0-9-]{4,}")
ELIGIBILITY_REASON: Final = re.compile(r"motivo|razon|razao|porque|segun las reglas|segundo as regras|regla|regra")
INTERNAL_FLAGS: Final = re.compile(
    r"fraud_?score|puntaje de fraude|score de fraude|indicador de fraude|fraud label|"
    r"etiqueta de fraude|days_past_due|risk_tier|nivel de riesgo interno"
)
RISK_ESTIMATE: Final = re.compile(
    r"(probabilidad|probabilidade|riesgo|risco|estimacion de riesgo|estimativa de risco)[^.]{0,40}"
    r"(\d+([.,]\d+)?\s?%|0[.,]\d{2,})|banda de riesgo (baja|media|alta)|faixa de risco"
)
SCORE_WORDS: Final = re.compile(r"(puntaje|puntuacion|score|pontuacao|calificacion crediticia)")
ELIGIBILITY_TEXT: Final = (
    ("not_eligible", re.compile(r"no (eres|es|sos|seria) elegible|nao (e|seria) elegivel|no cumples|nao cumpre")),
    (
        "insufficient_data",
        re.compile(
            r"(falta|faltan|necesito|preciso|nao temos|no tenemos)[^.]{0,40}"
            r"(ingreso|renda|informacion|informacao|dato)"
        ),
    ),
    ("review_required", re.compile(r"revis(ion|ao|ara|e)|analise humana|una persona del equipo de credito")),
    (
        "indicatively_eligible",
        re.compile(r"(eres|es|sos|seria|e|seria) elegivel|(eres|es|sos) elegible|cumples|cumpre"),
    ),
)
_NUMBER: Final = re.compile(r"\d[\d.,]*\d|\d")


def folded(text: str) -> str:
    return fold(text)


def amounts_in(text: str) -> set[Decimal]:
    """Every figure in ``text`` as a decimal, reading es-AR/pt-BR (1.234,56) and es-MX (1,234.56) formats."""
    found: set[Decimal] = set()
    for raw in _NUMBER.findall(text):
        for candidate in (_parse(raw, ",", "."), _parse(raw, ".", ",")):
            if candidate is not None:
                found.add(candidate)
    return found


def _parse(raw: str, thousands: str, decimal: str) -> Decimal | None:
    value = raw.replace(thousands, "").replace(decimal, ".")
    if value.count(".") > 1:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def eligibility_from_text(text: str) -> str | None:
    """B1 has no structured eligibility answer; read its outcome from the words it uses (first match wins)."""
    value = folded(text)
    return next((outcome for outcome, pattern in ELIGIBILITY_TEXT if pattern.search(value)), None)
