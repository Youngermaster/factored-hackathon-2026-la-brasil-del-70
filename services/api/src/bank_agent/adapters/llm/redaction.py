"""Masking personal data in prompt variables before they leave the process (CLAUDE.md rule 6).

Every variable whose key is not in the allowlist is scrubbed: emails, Mexican CURP, Brazilian CPF and CNPJ,
document numbers introduced by a keyword (CC, cedula, DNI, CPF, RG, documento, pasaporte), card numbers,
phone numbers, dot-grouped numbers that look like Argentine DNI or Colombian CC, long digit runs, the session's
sensitive terms (for example the first name), and names introduced by phrases such as "me llamo" or "meu nome
e". Each match becomes a labeled marker such as ``[EMAIL]``.

The rules differ from the log redaction in ``bootstrap/logging.py`` on purpose: prompts need amounts, so a
dot-grouped number or a long digit run preceded by a currency marker or followed by a currency word is kept
(``$1.500.000``, ``1.500.000 pesos``). Masking is deterministic and idempotent, so the cassette client can
apply it again and get the same key.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from pydantic import JsonValue

from bank_agent.domain.intelligence import PromptValue

UNREDACTED_VARIABLE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "actions_taken",
        "clause_texts",
        "dialect_hint",
        "disclaimer",
        "eligibility_outcome",
        "eligibility_reasons",
        "escalation_reason",
        "reference_date",
        "response_kind",
        "router_candidates",
        "workflow",
    }
)
"""Variables written by deterministic code or taken from the synthetic policy pack; they never hold customer
text or record text, so they pass unchanged. Every other key is scrubbed."""

_CURRENCY_BEFORE = re.compile(r"(?:\$|R\$|US\$|COP|MXN|ARS|USD|BRL)\s*$", re.IGNORECASE)
_CURRENCY_AFTER = re.compile(
    r"^\s*(?:pesos|peso|reais|real|d[oó]lares|d[oó]lar|mxn|cop|ars|usd|brl|mil\b)", re.IGNORECASE
)
_NAME_WORD = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇÑÜ][a-záéíóúâêôãõçñü]+"


@dataclass(frozen=True, slots=True)
class _Rule:
    label: str
    pattern: re.Pattern[str]
    keep_amounts: bool = False
    group: str | None = None
    """When set, only this named group is replaced and the rest of the match is kept."""


_RULES: Final[tuple[_Rule, ...]] = (
    _Rule("EMAIL", re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")),
    _Rule("DOCUMENT", re.compile(r"(?<![A-Za-z0-9])[A-Z]{4}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d(?![A-Za-z0-9])")),
    _Rule("DOCUMENT", re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")),
    _Rule("DOCUMENT", re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}(?!\d)")),
    _Rule(
        "DOCUMENT",
        re.compile(
            r"(?i:(?<![A-Za-z])(?:c\.\s?c\.?|cc|c[ée]dula(?:\s+de\s+ciudadan[íi]a)?|dni|cpf|rg|curp|rfc|pasaporte"
            r"|passaporte|documento(?:\s+de\s+identidad)?|identidade|identificaci[óo]n))(?![A-Za-z])"
            r"(?:\s*(?i:n[°ºo.]?|n[úu]mero|nro\.?|#|:|es|é|e))*\s*"
            r"(?P<number>\d[\d.\-]{3,18}\d)(?!\d)"
        ),
        group="number",
    ),
    _Rule("CARD_NUMBER", re.compile(r"(?<![\d.+])(?:\d[ -]?){12,18}\d(?![\d.])")),
    _Rule(
        "PHONE",
        re.compile(r"(?<![\w+$])(?:\+\d{1,3}[ .-]?)?\(?\d{2,4}\)?[ .-]\d{3,5}[ .-]?\d{4}(?![\d.,])"),
    ),
    _Rule("PHONE", re.compile(r"(?<![\w])\+\d{10,14}(?!\d)")),
    _Rule("DOCUMENT", re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3}){2,3}(?![\d.,])"), keep_amounts=True),
    _Rule("NUMBER", re.compile(r"(?<![\w.,-])\d{8,}(?![\w,-]|\.\d)"), keep_amounts=True),
    _Rule(
        "NAME",
        re.compile(
            r"(?i:\b(?:me\s+llamo|mi\s+nombre\s+es|meu\s+nome\s+[ée]|me\s+chamo|a\s+nombre\s+de|em\s+nome\s+de"
            r"|soy|sou|se[ñn]ora?|sra?\.|dona|don|senhora?)\s+)"
            rf"(?P<name>{_NAME_WORD}(?:\s+(?:de\s+la\s+|de\s+los\s+|de\s+|da\s+|do\s+|dos\s+|das\s+|del\s+)?{_NAME_WORD}){{0,3}})"
        ),
        group="name",
    ),
)


def _is_amount(text: str, start: int, end: int) -> bool:
    return bool(_CURRENCY_BEFORE.search(text[max(0, start - 6) : start]) or _CURRENCY_AFTER.match(text[end:]))


def _replacer(rule: _Rule, text: str) -> Callable[[re.Match[str]], str]:
    def replace(match: re.Match[str]) -> str:
        if rule.keep_amounts and _is_amount(text, match.start(), match.end()):
            return match[0]
        marker = f"[{rule.label}]"
        if rule.group is None:
            return marker
        offset = match.start()
        start, end = match.start(rule.group) - offset, match.end(rule.group) - offset
        return match[0][:start] + marker + match[0][end:]

    return replace


class Redactor:
    """Scrubs personal data from prompt variables, text, and JSON; keys in ``allowlist`` pass unchanged."""

    def __init__(self, allowlist: frozenset[str] = UNREDACTED_VARIABLE_KEYS) -> None:
        self.allowlist = allowlist

    def redact_text(self, text: str, sensitive_terms: Sequence[str] = ()) -> str:
        for rule in _RULES:
            text = rule.pattern.sub(_replacer(rule, text), text)
        # Sensitive terms last, so an email or a document that contains a name is masked as a whole first.
        for term in sorted({term.strip() for term in sensitive_terms if term.strip()}, key=len, reverse=True):
            text = re.sub(rf"(?<!\w){re.escape(term)}(?!\w)", "[NAME]", text, flags=re.IGNORECASE)
        return text

    def redact_value(self, value: PromptValue, sensitive_terms: Sequence[str] = ()) -> PromptValue:
        if isinstance(value, str):
            return self.redact_text(value, sensitive_terms)
        if isinstance(value, Sequence) and not isinstance(value, str):
            return [self.redact_text(str(item), sensitive_terms) for item in value]
        return value

    def redact_variables(
        self, variables: Mapping[str, PromptValue], sensitive_terms: Sequence[str] = ()
    ) -> dict[str, PromptValue]:
        return {
            key: value if key in self.allowlist else self.redact_value(value, sensitive_terms)
            for key, value in variables.items()
        }

    def redact_json(self, value: JsonValue, sensitive_terms: Sequence[str] = ()) -> JsonValue:
        """Scrub every string leaf of a JSON value (used for model outputs written to cassettes)."""
        if isinstance(value, str):
            return self.redact_text(value, sensitive_terms)
        if isinstance(value, list):
            return [self.redact_json(item, sensitive_terms) for item in value]
        if isinstance(value, dict):
            return {key: self.redact_json(item, sensitive_terms) for key, item in value.items()}
        return value
