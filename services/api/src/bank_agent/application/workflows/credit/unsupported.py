"""Credit requests the workflow does not handle (``CRE-ALL-3``): limit increases, restructuring or refinancing,
disbursements, a request for a decision now, a request to see the credit score, and a request to withdraw an
application. A decision request also cites the ``CRE-ALL-1`` disclaimer and offers the review path; a score request
cites ``ELG-ALL-2`` and ``ELG-ALL-1`` (the estimate is never shown and the score is never read); the others offer a
person from the credit team. The chat has no withdraw action, so a withdrawal goes to a person."""

import re

from bank_agent.application.engine.definition import UnsupportedRequest
from bank_agent.application.understanding.text import fold

_NOW = r"(ya|ja|ahora|agora|logo|hoy|hoje|de una|ya mismo|right now|now)\b"
"""An immediacy word: with an approval verb it asks for a decision now, not for the requirements."""

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "limit_increase",
        re.compile(
            r"\baument\w* (de |del |el |mi |o |do |a |la |meu )?(limite|cupo)|\bsubir (el |mi |o |meu )?(limite|cupo)|"
            # QA 2026-10-05 (CRE-15): the subjunctive "que me suban el límite", "elevar o meu limite".
            r"\bsub\w* (de |del |el |mi |o |do |a |la |meu )?(limite|cupo)|"
            r"\b(elevar|ampliar) (o |el |a |la )?(meu |mi |minha )?(limite|cupo)|"
            r"\bmais limite\b|\bmas cupo\b|\bincrease my limit\b|\bhigher limit\b"
        ),
    ),
    ("restructuring", re.compile(r"refinanc|reestructur|reestrutur|renegoci|portabilidad|restructur")),
    (
        "disbursement",
        re.compile(
            r"desembols|\bliber(ar|en|e) (el |o )?(dinero|dinheiro|credito)|\bdeposit(en|ar|em) (el |o )?"
            r"(prestamo|emprestimo|dinero|dinheiro)|\bdisburse"
        ),
    ),
    (
        "decision_now",
        re.compile(
            r"\b(aprobame|aprobamelo|aprobalo|apruebame|apruebamelo|apruebelo|apruebenlo|apruebenmelo|aproveme|"
            r"aprove-me|me aprova|just approve|approve it)\b|"
            r"\b(aproba|aprueba|aprueben|aprove|aprova|aprovem|approve)\b(?! .*\?)(\s+\w+){0,4}?\s+"
            + _NOW
            + r"|\b(dame|denme|me den|me de|me da) (el |la |o |a )?(credito|prestamo|emprestimo|tarjeta|cartao) "
            r"(ya|ahora|agora|de una)\b|\bdecid(an|ir|e) (ya|ahora|agora)\b|\bdecisao (agora|ja)\b"
        ),
    ),
    # QA 2026-10-05 (CRE-08): a credit score question is abstained; the score is never read or shown.
    ("score_request", re.compile(r"\bscore\b|\bpuntaje\b|\bpontuacao\b|\bburo\b")),
    # QA 2026-10-05 (CRE-12): the chat has no withdraw action, so a withdrawal request goes to a person.
    (
        "withdrawal",
        re.compile(
            r"\b(retirar|retiren|retirem|cancelar|cancelen|cancelem|anular|desistir|desisto)( de| do| da)? "
            r"(la |a |el |o |esa |essa |esta )?(mi |minha |meu )?(solicitud|solicitacao|pedido)\b"
            r"(?! de (aclaracion|reclam|disputa|contestac|reposicion|desbloqueo|segunda via))"
        ),
    ),
)
TEMPLATES = {"decision_now": "credit.no_decision"}
CLAUSES = {"decision_now": ("CRE-ALL-3", "CRE-ALL-1"), "score_request": ("ELG-ALL-2", "ELG-ALL-1")}


def recognize(text: str) -> UnsupportedRequest | None:
    folded = fold(text)
    for code, pattern in _PATTERNS:
        if pattern.search(folded):
            return UnsupportedRequest(
                code=code,
                clauses=CLAUSES.get(code, ("CRE-ALL-3",)),
                template=TEMPLATES.get(code, "common.unsupported_in_workflow"),
            )
    return None
