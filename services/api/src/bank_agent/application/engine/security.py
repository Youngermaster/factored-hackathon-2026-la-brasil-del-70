"""Untrusted-content checks: heuristic prompt-injection patterns and record identifiers named in the text.

``detect_injection`` (``injection:heuristic@1``) runs on customer text and on record text (merchant names) in
Spanish, Portuguese, and English. It never blocks by itself: text stays data whatever it says, because no text can
select a state or a tool. A hit on customer text adds an ``injection_detected`` trust event; a hit on record text is
recorded as a safety intervention only (the customer did not write it). ``referenced_ids`` finds transaction,
product, customer, case, and credit application identifiers so the engine can check them against the session's
own records.
"""

import re
from dataclasses import dataclass

from bank_agent.application.understanding.text import fold

INJECTION_DETECTOR = "injection:heuristic@1"
_INJECTION: dict[str, re.Pattern[str]] = {
    "ignore_rules": re.compile(
        r"\b(ignora|ignore|ignorar|olvida|esquece|desconsidera|disregard|forget)\b.{0,40}"
        r"\b(instruc\w*|instruction\w*|regla\w*|regra\w*|rules?|prompt|anterior\w*|previous|politica\w*|policy)"
    ),
    "role_change": re.compile(
        r"\b(ahora eres|a partir de ahora eres|you are now|agora voce e|actua como|atue como|act as|finge que|"
        r"pretend to be|modo desarrollador|developer mode)\b"
    ),
    "prompt_disclosure": re.compile(
        r"\b(system prompt|prompt del sistema|prompt do sistema|tus instrucciones|suas instrucoes|"
        r"your instructions|revela tu prompt)\b"
    ),
    "delimiter_forgery": re.compile(r"</?data\b|<\|?(system|im_start|assistant)|\[/?inst\]|#{2,}\s*(system|instruc)"),
    "tool_invocation": re.compile(
        r"\b(call|llama|chama|ejecuta|execute|executa|invoke|usa|use)\b.{0,30}"
        r"\b(tool|herramienta|ferramenta|function|funcion|funcao)\b"
        r"|\b(block_card|create_dispute_case|submit_credit_application|get_my_credit_profile|list_my_cards)\b"
    ),
    "other_customer": re.compile(
        r"\b(customer_id|customer id|id de cliente|otro cliente|outro cliente|another customer)\b"
    ),
}
_IDS = re.compile(r"\b(?:TRX|TXN|PRD|CLI|CUS)-[A-Z0-9][A-Z0-9-]{3,29}\b|\b(?:case|app)-[0-9a-z]{6,59}\b", re.IGNORECASE)


def detect_injection(text: str) -> tuple[str, ...]:
    """The names of the injection patterns ``text`` matches, in a fixed order."""
    folded = fold(text)
    return tuple(name for name, pattern in _INJECTION.items() if pattern.search(folded))


@dataclass(frozen=True)
class ReferencedIds:
    transactions: tuple[str, ...] = ()
    products: tuple[str, ...] = ()
    customers: tuple[str, ...] = ()
    cases: tuple[str, ...] = ()
    applications: tuple[str, ...] = ()

    @property
    def any(self) -> bool:
        return bool(self.transactions or self.products or self.customers or self.cases or self.applications)


def referenced_ids(text: str) -> ReferencedIds:
    found = [match.group(0) for match in _IDS.finditer(text)]
    upper = [value.upper() for value in found]
    return ReferencedIds(
        transactions=tuple(dict.fromkeys(v for v in upper if v.startswith(("TRX-", "TXN-")))),
        products=tuple(dict.fromkeys(v for v in upper if v.startswith("PRD-"))),
        customers=tuple(dict.fromkeys(v for v in upper if v.startswith(("CLI-", "CUS-")))),
        cases=tuple(dict.fromkeys(v.lower() for v in found if v.lower().startswith("case-"))),
        applications=tuple(dict.fromkeys(v.lower() for v in found if v.lower().startswith("app-"))),
    )
