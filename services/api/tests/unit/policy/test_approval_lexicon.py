"""The approval-wording lexicon shared by the pack loader, the eligibility renderer, the grounding verifier, and
the evaluation's credit-safety grader: approval and qualification claims in es, pt, and en are found, even
negated, and the indicative eligibility wording P uses is not."""

import pytest

from bank_agent.application.engine.templates import TEMPLATES
from bank_agent.application.workflows.baseline import templates as baseline_templates
from bank_agent.domain.locale import Language
from bank_agent.policy.lexicon import approval_terms

del baseline_templates

CLAIMS = [
    "Tu préstamo fue aprobado.",
    "Estás preaprobado para la tarjeta.",
    "Quedaste pre-aprobada.",
    "¡Felicidades, estás calificado!",
    "Estás calificada para un préstamo personal.",
    "Con ese ingreso calificas para el crédito.",
    "Estás cualificado para la tarjeta.",
    "Te precalificamos para el préstamo.",
    "Estás habilitado para obtener el crédito.",
    "Estás apto para el préstamo.",
    "Tu crédito ya está liberado.",
    "Não estás aprovado ainda.",
    "Seu empréstimo foi aprovado.",
    "Você é elegível para aprovação.",
    "Você está qualificada para o cartão.",
    "Você se qualifica para o empréstimo.",
    "Seu limite foi liberado.",
    "O crédito já está garantido.",
    "Você está apta a receber o empréstimo.",
    "You are pre-qualified.",
    "You qualify for the card.",
    "You are eligible for the loan.",
    "This is not an approval.",
]
LEGITIMATE = [
    "Según las reglas sintéticas, tu perfil cumple de forma indicativa las condiciones de este producto.",
    "Según las reglas sintéticas, tu perfil no cumple por ahora las condiciones indicativas de este producto.",
    "Segundo as regras sintéticas, o seu perfil atende de forma indicativa às condições deste produto.",
    "Segundo as regras sintéticas, o seu perfil ainda não atende às condições indicativas deste produto.",
    "A estimativa de risco está em uma faixa aceitável.",
    "Orientación sintética de elegibilidad (demostración): no es una decisión de crédito.",
    "Tu calificación crediticia no se muestra en esta conversación.",
    "Una persona del equipo de crédito revisa tu caso.",
    "Tu tarjeta está activa.",
]


@pytest.mark.parametrize("text", CLAIMS)
def test_approval_and_qualification_claims_are_found(text: str) -> None:
    assert approval_terms(text) != (), text


@pytest.mark.parametrize("text", LEGITIMATE)
def test_indicative_wording_is_not_an_approval_claim(text: str) -> None:
    assert approval_terms(text) == (), text


def test_every_engine_template_passes_the_extended_lexicon() -> None:
    offending = [
        (name, language)
        for name, texts in TEMPLATES.items()
        for language in (Language.ES, Language.PT, Language.EN)
        if approval_terms(texts[language])
    ]
    assert offending == []
