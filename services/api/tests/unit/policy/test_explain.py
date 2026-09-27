"""The explanation renderer and the approval lexicon."""

from decimal import Decimal

import pytest

from bank_agent.domain.decision import ClauseRef, DecisionKind
from bank_agent.domain.errors import PolicyPackInvalidError
from bank_agent.domain.locale import Language, Locale
from bank_agent.domain.money import Currency, Money
from bank_agent.policy.evaluator import evaluate
from bank_agent.policy.explain import decision_refs, explain, explain_decision, format_money, format_number, render_body
from bank_agent.policy.facts import EscalationSignals
from bank_agent.policy.lexicon import approval_terms
from bank_agent_policy import clause, facts, fixture_pack, request


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        (Locale.ES_MX, "2,000,000.00 COP"),
        (Locale.EN_US, "2,000,000.00 COP"),
        (Locale.ES_CO, "2.000.000,00 COP"),
        (Locale.ES_AR, "2.000.000,00 COP"),
        (Locale.PT_BR, "2.000.000,00 COP"),
    ],
)
def test_money_uses_the_locale_separators(locale: Locale, expected: str) -> None:
    assert format_money(Money.of("2000000", Currency.COP), locale) == expected


def test_numbers_round_to_the_requested_places_and_keep_the_sign() -> None:
    assert format_number(Decimal("-1234.5"), Locale.ES_MX, 2) == "-1,234.50"
    assert format_number(Decimal("999"), Locale.PT_BR, 0) == "999"


def test_a_body_is_rendered_with_its_parameters() -> None:
    rendered = render_body(
        clause(
            "DSP-MX-3",
            params={"auto_intake_max_amount": Money.of("10000.00", Currency.MXN), "days": 90},
            body="Up to {auto_intake_max_amount} within {days} days.",
        ),
        Locale.ES_MX,
    )
    assert rendered == "Up to 10,000.00 MXN within 90 days."


def test_a_placeholder_that_cannot_be_rendered_is_a_pack_error() -> None:
    with pytest.raises(PolicyPackInvalidError):
        render_body(clause("CRD-ALL-2", params={"flag": True}, body="Flag {flag}."), Locale.EN_US)


def test_a_decision_is_explained_by_its_decisive_clauses_in_the_session_language() -> None:
    pack = fixture_pack()
    decision = evaluate(request(facts_=facts(escalation=EscalationSignals(human_requested=True))), pack)
    assert decision.kind is DecisionKind.ESCALATE
    rendered = explain_decision(pack, decision, Language.PT, Locale.PT_BR)
    assert rendered.citations == (ClauseRef.parse("ESC-ALL-1@1"),)
    assert rendered.text == "[fixture pt] ESC-ALL-1"
    assert rendered.language is Language.PT


def test_without_decisive_rules_the_workflow_clauses_explain() -> None:
    pack = fixture_pack()
    decision = evaluate(request(facts_=facts()), pack).model_copy(
        update={"decisive_rule_ids": (), "kind": DecisionKind.ALLOW}
    )
    assert {ref.family for ref in decision_refs(decision)} <= {"DSP", "CRD", "ACC", "CRE", "INF"}


def test_explain_renders_exact_versions_once_each() -> None:
    pack = fixture_pack()
    ref = ClauseRef.parse("CRE-ALL-1@1")
    assert explain(pack, [ref, ref], Language.EN, Locale.EN_US).citations == (ref,)


@pytest.mark.parametrize(
    "text",
    [
        "Tu crédito fue aprobado",
        "No es una preaprobación",
        "Crédito otorgado",
        "Seu crédito foi aprovado",
        "Não é uma aprovação",
        "This is not an approval",
        "Credit granted",
        "PRE-APPROVED",
    ],
)
def test_approval_wording_is_found_in_every_language_and_form(text: str) -> None:
    assert approval_terms(text)


def test_neutral_credit_wording_passes() -> None:
    assert approval_terms("Orientación indicativa: no es una oferta ni una decisión de crédito.") == ()
