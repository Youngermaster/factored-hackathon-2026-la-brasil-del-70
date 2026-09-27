"""Golden texts for every template in Spanish and Portuguese, each also clean for the grounding verifier.

Regenerate with ``UPDATE_TEMPLATE_GOLDEN=1`` after an intended wording change, and review the diff.
"""

import os
import re
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from bank_agent.application.engine.render import fill
from bank_agent.application.engine.reply import Choices, Masked, Param, RecordText
from bank_agent.application.engine.templates import TEMPLATES
from bank_agent.application.grounding.draft import GroundingContext, ResponseDraft, VerifiedAction
from bank_agent.application.grounding.verifier import GroundingVerifier
from bank_agent.application.workflows.baseline import templates as baseline_templates
from bank_agent.domain.actions import ActionKind, ActionResult, ActionStatus, Verification
from bank_agent.domain.identifiers import IdempotencyKey, SourceRef
from bank_agent.domain.locale import Country, Language, Locale
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import WorkflowId
from bank_agent_policy import fixture_pack

GOLDEN = Path(__file__).parent / "golden"
SAMPLES: dict[str, Param] = {
    "capabilities": "tarjetas y reclamaciones",
    "first": "tus tarjetas",
    "second": "una reclamación",
    "pending": "tu reclamación",
    "target": "tus tarjetas",
    "due": date(2026, 8, 2),
    "date": date(2026, 6, 15),
    "expires": date(2028, 3, 31),
    "merchant": RecordText("FIXTURE MARKET"),
    "amount": Money.of("1250.00", Currency.MXN),
    "card": Masked("1234"),
    "reason": "no reconoces la compra",
    "case": "case-000001",
    "status": "abierto",
    "type": "tarjeta de crédito",
    "expression": RecordText("03/04"),
    "n": 1,
}
LIST_ITEMS = {
    "card.clarify_options": ("options", "card.option"),
    "card.declined": ("items", "card.declined_item"),
    "dispute.clarify_options": ("options", "dispute.option"),
    "dispute.status_many": ("items", "dispute.status_item"),
}
LOCALIZED: dict[Language, dict[str, Param]] = {
    Language.ES: {},
    Language.PT: {
        "capabilities": "cartões e contestações",
        "first": "os seus cartões",
        "second": "uma contestação",
        "pending": "a sua contestação",
        "target": "os seus cartões",
        "reason": "você não reconhece a compra",
        "status": "aberto",
        "type": "cartão de crédito",
    },
}
AT = datetime(2026, 6, 18, 15, 0, tzinfo=UTC)
del baseline_templates


def params_for(template: str, language: Language) -> dict[str, Param]:
    names = set(re.findall(r"\{([a-z]+)\}", TEMPLATES[template][Language.ES]))
    samples = {**SAMPLES, **LOCALIZED[language]}
    params: dict[str, Param] = {name: samples[name] for name in names if name in samples}
    if template in LIST_ITEMS:
        name, item = LIST_ITEMS[template]
        fields = set(re.findall(r"\{([a-z]+)\}", TEMPLATES[item][Language.ES])) - {"n"}
        row: dict[str, Param] = {field: samples[field] for field in fields}
        params[name] = Choices(item, (row, row))
    return params


def verified(action: ActionKind) -> VerifiedAction:
    evidence = SourceRef.model_validate("dispute_cases:case-000001")
    return VerifiedAction(
        result=ActionResult(
            action=action,
            idempotency_key=IdempotencyKey("wf-fixture-golden-0001"),
            status=ActionStatus.EXECUTED,
            outcome_ref=evidence,
            attempts=1,
            completed_at=AT,
        ),
        verification=Verification(verified=True, check="fixture", evidence=evidence, checked_at=AT),
    )


@pytest.mark.parametrize("language", [Language.ES, Language.PT])
def test_every_template_matches_its_golden_text_and_passes_the_verifier(language: Language) -> None:
    locale = Locale.ES_MX if language is Language.ES else Locale.PT_BR
    verifier = GroundingVerifier(fixture_pack())
    actions = (verified(ActionKind.CREATE_DISPUTE_CASE), verified(ActionKind.BLOCK_CARD))
    lines: list[str] = []
    for template in sorted(TEMPLATES):
        assert TEMPLATES[template].keys() >= {Language.ES, Language.PT, Language.EN}
        filled = fill(template, params_for(template, language), language, locale)
        assert "{" not in filled.text, template
        context = GroundingContext(
            workflow=WorkflowId.DISPUTE,
            language=language,
            jurisdiction=Country.MX,
            currency=Currency.MXN,
            facts=tuple(fact.evolve(fact_id=f"f{i}") for i, fact in enumerate(filled.facts)),
            actions=actions,
        )
        assert verifier.verify(ResponseDraft(text=filled.check), context) == (), template
        lines.append(f"[{template}]\n{filled.text}\n")
    path = GOLDEN / f"templates.{language.value}.txt"
    text = "\n".join(lines)
    if os.environ.get("UPDATE_TEMPLATE_GOLDEN") == "1":
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == text
