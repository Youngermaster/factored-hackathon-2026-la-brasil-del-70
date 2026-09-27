"""Turn a ``Reply`` into an ``AssistantResponse``: fill the template, append the rendered clauses, and verify.

Every reply is checked by the grounding verifier before it is returned. The evidence is what deterministic code
supplied: the typed parameters (amounts, dates, counts, masked numbers, all read from verified records), the
reply's record facts, the clauses bound to the state, the cited clauses, and the verified actions of the turn.
Record text is replaced by a neutral placeholder for the check, so a merchant name can never be read as a claim.
Violations are stored in the execution record. Optional language model phrasing (``phrase.py``) must pass the same
check or the template text is used.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from bank_agent.application.engine.reply import Choices, Masked, Param, RecordText, Reply
from bank_agent.application.engine.templates import TEMPLATES
from bank_agent.application.grounding.draft import (
    FactKind,
    GroundingContext,
    RecordFact,
    ResponseDraft,
    VerifiedAction,
    Violation,
)
from bank_agent.application.grounding.verifier import GroundingVerifier
from bank_agent.domain.conversation import AssistantResponse, Citation
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.locale import Country, Language, Locale
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import WorkflowId
from bank_agent.policy.explain import explain, format_money
from bank_agent.policy.pack import PolicyPack

RECORD_PLACEHOLDER = "[dato]"
MAX_TEXT = 4000
MAX_RECORD_TEXT = 80
MAX_EXCERPT = 1000
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
MONTH_NAMES = {
    Language.ES: ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
                  "noviembre", "diciembre"),
    Language.PT: ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
                  "novembro", "dezembro"),
}  # fmt: skip


def format_date(value: date, language: Language) -> str:
    names = MONTH_NAMES.get(language)
    if names is None:
        return value.isoformat()
    return f"{value.day} de {names[value.month - 1]} de {value.year}"


def clean_record_text(text: str) -> str:
    return _CONTROL.sub(" ", text).strip()[:MAX_RECORD_TEXT]


@dataclass
class Filled:
    text: str
    check: str
    facts: list[RecordFact]


class _Filler:
    def __init__(self, language: Language, locale: Locale) -> None:
        self.language, self.locale = language, locale
        self.facts: list[RecordFact] = []

    def _fact(self, kind: FactKind, **value: object) -> None:
        self.facts.append(RecordFact.model_validate({"fact_id": f"p{len(self.facts) + 1}", "kind": kind, **value}))

    def value(self, param: Param) -> tuple[str, str]:
        if isinstance(param, Money):
            self._fact(FactKind.AMOUNT, money=param)
            text = format_money(param, self.locale)
            return text, text
        if isinstance(param, date):
            self._fact(FactKind.DATE, day=param)
            text = format_date(param, self.language)
            return text, text
        if isinstance(param, bool):
            raise TypeError("booleans are not template parameters")
        if isinstance(param, int):
            self._fact(FactKind.COUNT, number=param)
            return str(param), str(param)
        if isinstance(param, RecordText):
            return clean_record_text(param.text), RECORD_PLACEHOLDER
        if isinstance(param, Masked):
            if param.last4.isdigit():
                self._fact(FactKind.REFERENCE, reference=param.last4)
            text = f"**** {param.last4}"
            return text, text
        if isinstance(param, Choices):
            lines = [self.fill(param.template, {"n": index, **item}) for index, item in enumerate(param.items, 1)]
            return "\n".join(line[0] for line in lines), "\n".join(line[1] for line in lines)
        return param, param

    def fill(self, template: str, params: dict[str, Param]) -> tuple[str, str]:
        text = check = TEMPLATES[template][self.language]
        for name, param in params.items():
            shown, verified = self.value(param)
            text = text.replace("{" + name + "}", shown)
            check = check.replace("{" + name + "}", verified)
        return text, check


def fill(template: str, params: dict[str, Param], language: Language, locale: Locale) -> Filled:
    filler = _Filler(language, locale)
    text, check = filler.fill(template, params)
    return Filled(text=text, check=check, facts=filler.facts)


@dataclass(frozen=True)
class RenderInput:
    language: Language
    locale: Locale
    jurisdiction: Country
    workflow: WorkflowId | None
    currency: Currency | None
    bound: tuple[ClauseRef, ...]
    actions: tuple[VerifiedAction, ...]


@dataclass(frozen=True)
class Rendered:
    response: AssistantResponse
    check_text: str
    context: GroundingContext
    citations: tuple[ClauseRef, ...]
    violations: tuple[Violation, ...]
    clause_texts: tuple[str, ...]


class Renderer:
    def __init__(self, pack: PolicyPack, verifier: GroundingVerifier) -> None:
        self._pack = pack
        self._verifier = verifier

    def _explanation(self, refs: Sequence[ClauseRef], language: Language, locale: Locale, room: int) -> list[str]:
        paragraphs: list[str] = []
        for ref in dict.fromkeys(refs):
            text = explain(self._pack, (ref,), language, locale).text
            if len(text) + 2 > room:
                break
            paragraphs.append(text)
            room -= len(text) + 2
        return paragraphs

    def render(self, reply: Reply, given: RenderInput) -> Rendered:
        languages = (Language.ES, Language.PT) if reply.bilingual else (given.language,)
        parts = [fill(reply.template, reply.params, language, given.locale) for language in languages]
        if reply.prefix is not None:
            parts.insert(0, fill(reply.prefix, reply.params, given.language, given.locale))
        parts.extend(fill(template, params, given.language, given.locale) for template, params in reply.suffix)
        text = "\n".join(part.text for part in parts)
        check = "\n".join(part.check for part in parts)
        paragraphs = self._explanation(reply.explain, given.language, given.locale, MAX_TEXT - len(text))
        appended = tuple(dict.fromkeys(reply.explain))[: len(paragraphs)]
        inline = tuple(ref for ref in dict.fromkeys(reply.cite) if ref not in appended)
        cited = (*appended, *inline)
        full, full_check = "\n\n".join([text, *paragraphs]), "\n\n".join([check, *paragraphs])
        facts = (*reply.facts, *(fact for part in parts for fact in part.facts))
        credit = reply.credit
        context = GroundingContext(
            workflow=given.workflow,
            language=given.language,
            jurisdiction=given.jurisdiction,
            currency=given.currency,
            facts=_unique_ids(facts),
            bound_clauses=given.bound,
            actions=given.actions,
            eligibility=credit.assessment if credit is not None else None,
            catalog_product=credit.product if credit is not None else None,
            credit_profile=credit.profile if credit is not None else None,
            risk_estimate=credit.estimate if credit is not None else None,
            declared_income=credit.declared_income if credit is not None else None,
        )
        violations = self._verifier.verify(ResponseDraft(text=full_check, citations=cited), context)
        excerpts = (*paragraphs, *(explain(self._pack, (ref,), given.language, given.locale).text for ref in inline))
        citations = tuple(
            Citation(clause=ref, excerpt=excerpt[:MAX_EXCERPT]) for ref, excerpt in zip(cited, excerpts, strict=True)
        )
        response = AssistantResponse(
            language=given.language,
            text=full[:MAX_TEXT],
            template_id=reply.template,
            citations=citations,
            clarification=reply.clarification,
            confirmation=reply.confirmation,
            card_action_confirmation=reply.card_action_confirmation,
            action_statuses=reply.action_statuses,
            escalation=reply.escalation,
            step_up_required=reply.step_up_required,
            notices=reply.notices,
            card_status=reply.card_status,
        )
        return Rendered(response, full_check, context, cited, violations, tuple(paragraphs))


def _unique_ids(facts: Sequence[RecordFact]) -> tuple[RecordFact, ...]:
    return tuple(fact.evolve(fact_id=f"f{index}") for index, fact in enumerate(facts, 1))
