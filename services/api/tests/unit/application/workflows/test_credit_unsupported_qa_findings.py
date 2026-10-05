"""Credit unsupported-request regressions from the production QA pass of 2026-10-05 (finding ids in names)."""

import pytest

from bank_agent.application.understanding.extraction import dispute_reason
from bank_agent.application.understanding.slots import credit_product_type
from bank_agent.application.workflows.credit.unsupported import recognize
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.dispute import DisputeReason


@pytest.mark.parametrize("text", ["que me suban el límite", "me sube el cupo", "quero elevar o meu limite"])
def test_cre15_limit_increase_wordings_are_unsupported(text: str) -> None:
    found = recognize(text)
    assert found is not None
    assert (found.code, found.clauses) == ("limit_increase", ("CRE-ALL-3",))


@pytest.mark.parametrize(
    "text", ["¿Cuál es mi puntaje de crédito?", "Qual é a minha pontuação de crédito?", "¿Cómo estoy en el buró?"]
)
def test_cre08_score_questions_are_abstained_with_the_risk_estimate_clauses(text: str) -> None:
    found = recognize(text)
    assert found is not None
    assert (found.code, found.clauses, found.template) == (
        "score_request",
        ("ELG-ALL-2", "ELG-ALL-1"),
        "common.unsupported_in_workflow",
    )


@pytest.mark.parametrize(
    "text", ["Quiero retirar mi solicitud", "Quero cancelar a minha solicitação", "Quero desistir do pedido"]
)
def test_cre12_withdrawal_requests_go_to_a_person(text: str) -> None:
    found = recognize(text)
    assert found is not None
    assert (found.code, found.clauses, found.template) == (
        "withdrawal",
        ("CRE-ALL-3",),
        "common.unsupported_in_workflow",
    )


@pytest.mark.parametrize(
    "text", ["Quiero cancelar mi solicitud de aclaración", "Cancelé mi pedido en la tienda y me cobraron igual"]
)
def test_cre12_dispute_and_purchase_cancellations_are_not_withdrawals(text: str) -> None:
    assert recognize(text) is None


@pytest.mark.parametrize(
    ("text", "product"),
    [
        ("préstamo de libre inversión", CreditProductType.PERSONAL_LOAN),
        ("Quero financiar um apartamento", CreditProductType.MORTGAGE),
    ],
)
def test_cre02_cre03_credit_product_slots_cover_regional_names(text: str, product: CreditProductType) -> None:
    assert credit_product_type(text) is product


@pytest.mark.parametrize(
    "text", ["quiero desconocer un consumo", "un cobro raro q yo no hize", "Quero desconhecer essa compra"]
)
def test_dsp05_colloquial_unrecognized_wordings_give_the_unrecognized_reason(text: str) -> None:
    assert dispute_reason(text) is DisputeReason.UNRECOGNIZED
