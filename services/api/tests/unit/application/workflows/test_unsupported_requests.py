"""In-domain unsupported requests: account requests abstained with ACC-ALL-3 and credit requests with CRE-ALL-3
(a decision request also with the CRE-ALL-1 disclaimer), in es and pt; supported requests are not caught."""

import pytest

from bank_agent.application.workflows.account_inquiry.unsupported import recognize as account
from bank_agent.application.workflows.credit.unsupported import recognize as credit


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Quero fazer uma transferência de 500 pesos para o João", "transfer"),
        ("Quiero hacer una transferencia a mi hermana", "transfer"),
        ("necesito transferir dinero", "transfer"),
        ("Transfiere 2000 pesos de mi cuenta de ahorro a la corriente", "transfer"),
        ("Transfira 2000 pesos da poupança para a conta corrente", "transfer"),
        ("Quiero pagar mi tarjeta de crédito desde aquí", "bill_payment"),
        ("quero pagar o boleto", "bill_payment"),
        ("¿Puedo cambiar la fecha de corte?", "due_date_change"),
        ("¿Cuál es mi fecha límite de pago?", "due_date"),
        ("necesito un certificado bancario", "certificate"),
    ],
)
def test_account_requests_the_workflow_does_not_handle(text: str, code: str) -> None:
    found = account(text)
    assert found is not None
    assert (found.code, found.clauses, found.template) == (code, ("ACC-ALL-3",), "common.unsupported_in_workflow")


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Quiero un aumento de límite de mi tarjeta", "limit_increase"),
        ("Quero aumentar o limite do meu cartão", "limit_increase"),
        ("quiero refinanciar mi préstamo", "restructuring"),
        ("quero renegociar a dívida", "restructuring"),
        ("desembolsen el préstamo hoy", "disbursement"),
        ("Aprobame el préstamo ya, dale", "decision_now"),
        ("me aprova agora", "decision_now"),
        ("dame el crédito ya", "decision_now"),
        ("Aprove o meu crédito agora", "decision_now"),
        ("Aprova meu empréstimo já", "decision_now"),
        ("Aprueba mi crédito ya", "decision_now"),
        ("Apruébame el préstamo ahora", "decision_now"),
        ("Quero que aprovem meu empréstimo agora", "decision_now"),
    ],
)
def test_credit_requests_the_workflow_does_not_handle(text: str, code: str) -> None:
    found = credit(text)
    assert found is not None
    assert found.code == code
    assert found.clauses[0] == "CRE-ALL-3"
    if code == "decision_now":
        assert (found.clauses, found.template) == (("CRE-ALL-3", "CRE-ALL-1"), "credit.no_decision")


@pytest.mark.parametrize(
    "text",
    ["¿cuál es mi saldo?", "situação da minha transferência", "¿me aprueban un préstamo?", "sou elegível?",
     "qué condiciones tiene el préstamo personal", "¿Qué necesito para que me aprueben un préstamo?",
     "O que preciso para ter um empréstimo aprovado?", "¿Me lo aprueban ya?"],
)  # fmt: skip
def test_supported_requests_are_not_caught(text: str) -> None:
    assert account(text) is None
    assert credit(text) is None


@pytest.mark.parametrize(
    "text", ["Transfiérame con un asesor", "me transfiera a un asesor", "Me transfere para um atendente"]
)
def test_a_request_to_be_transferred_to_a_person_is_not_a_money_transfer(text: str) -> None:
    assert account(text) is None
