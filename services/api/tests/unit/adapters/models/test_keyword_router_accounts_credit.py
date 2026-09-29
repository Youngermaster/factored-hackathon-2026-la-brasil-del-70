"""The keyword router on account and credit phrases (session 09b), in es and pt, above its threshold."""

import pytest

from bank_agent.adapters.models.keyword_router import KeywordIntentRouter
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent

ROUTER = KeywordIntentRouter()


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Hola, ¿me decís cuál es mi saldo?", Intent.BALANCE_INQUIRY),
        ("Qual é o saldo da minha conta?", Intent.BALANCE_INQUIRY),
        ("Qual é a situação da minha transferência de 1500 pesos?", Intent.PAYMENT_STATUS),
        ("¿Cuál es el estado de mi pago de ayer?", Intent.PAYMENT_STATUS),
        ("Quiero el estado de cuenta de mi tarjeta de crédito del mes pasado", Intent.STATEMENT_REQUEST),
        ("Quero o extrato do mês passado", Intent.STATEMENT_REQUEST),
        ("¿Qué condiciones tiene el préstamo personal?", Intent.CREDIT_PRODUCT_INFO),
        ("Quais produtos de crédito vocês têm?", Intent.CREDIT_PRODUCT_INFO),
        ("Quiero saber si califico para un préstamo personal", Intent.CREDIT_ELIGIBILITY),
        ("Sou elegível para um cartão de crédito?", Intent.CREDIT_ELIGIBILITY),
        ("Aprobame el préstamo ya", Intent.CREDIT_ELIGIBILITY),
        ("Posso pegar um empréstimo pessoal de 1.000.000 em 24 meses?", Intent.CREDIT_ELIGIBILITY),
        ("Pode me informar se tenho direito a um empréstimo pessoal?", Intent.CREDIT_ELIGIBILITY),
        ("¿Puedo obtener un préstamo personal de 50 mil?", Intent.CREDIT_ELIGIBILITY),
        ("Qual é a situação da minha solicitação?", Intent.CREDIT_APPLICATION_STATUS),
        ("Quero fazer uma transferência de 500 pesos", Intent.UNSUPPORTED),
        ("¿Cuál es mi fecha límite de pago?", Intent.UNSUPPORTED),
        ("quiero refinanciar mi préstamo", Intent.UNSUPPORTED),
    ],
)
def test_account_and_credit_phrases_route_above_the_threshold(text: str, intent: Intent) -> None:
    prediction = ROUTER.route(UntrustedText(text), Language.ES)
    assert prediction.intent is intent
    assert not prediction.below_threshold
