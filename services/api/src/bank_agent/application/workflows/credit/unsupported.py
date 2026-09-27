"""Credit requests the workflow does not handle (``CRE-ALL-3``): limit increases, restructuring or refinancing,
disbursements, and a request for a decision now. A decision request also cites the ``CRE-ALL-1`` disclaimer and
offers the review path; the others offer a person from the credit team."""

import re

from bank_agent.application.engine.definition import UnsupportedRequest
from bank_agent.application.understanding.text import fold

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "limit_increase",
        re.compile(
            r"\baument\w* (de |del |el |mi |o |do |a |la |meu )?(limite|cupo)|\bsubir (el |mi |o |meu )?(limite|cupo)|"
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
            r"\b(aprobame|aprobamelo|aprobalo|apruebame|apruebamelo|apruebelo|apruebenlo|apruebenmelo|aprueben|"
            r"aprovem|aprove|me aprova|aprova (ja|logo|agora)|just approve|approve it)\b|"
            r"\b(dame|denme|me den|me de|me da) (el |la |o |a )?(credito|prestamo|emprestimo|tarjeta|cartao) "
            r"(ya|ahora|agora|de una)\b|\bdecid(an|ir|e) (ya|ahora|agora)\b|\bdecisao (agora|ja)\b"
        ),
    ),
)
TEMPLATES = {"decision_now": "credit.no_decision"}
CLAUSES = {"decision_now": ("CRE-ALL-3", "CRE-ALL-1")}


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
