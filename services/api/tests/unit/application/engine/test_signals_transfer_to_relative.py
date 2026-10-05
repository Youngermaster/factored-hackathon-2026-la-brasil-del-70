"""Moving the customer's own money to a relative is not a third-party request (QA finding ACC-04).

The model flagged "Faz um pix de 300 reais pro meu irmão" as third party; the kernel refused it with PRV-ALL-2 and
the raised risk tier asked for step-up on the next read. With a transfer verb and the relative as the recipient,
the model's third-party flag is dropped. A relative's product or data is still third party, from the keywords.
"""

import pytest

from bank_agent.application.engine.signals import detect_signals
from bank_agent.domain.llm_outputs import EscalationSignals

MODEL_THIRD_PARTY = EscalationSignals(
    legal_or_regulator_mention=False, distress=False, human_requested=False, third_party_admission=True
)


@pytest.mark.parametrize(
    "text",
    [
        "Faz um pix de 300 reais pro meu irmão",
        "Pásale 2000 pesos a mi hermana de mi cuenta de cheques",
        "Quiero transferir 500 pesos a mi mamá",
        "Quero mandar dinheiro para minha mãe",
    ],
)
def test_a_transfer_to_a_relative_drops_the_model_third_party_flag(text: str) -> None:
    assert detect_signals(text).merged(MODEL_THIRD_PARTY).third_party_admission is False


@pytest.mark.parametrize(
    "text",
    [
        "Muéstrame el saldo de la cuenta de mi mamá",
        "Transfiere dinero de la cuenta de mi papá a la mía",
        "Qual é o saldo da conta corrente do meu pai?",
    ],
)
def test_a_relative_product_is_still_third_party(text: str) -> None:
    assert detect_signals(text).merged(MODEL_THIRD_PARTY).third_party_admission is True


def test_the_model_third_party_flag_still_counts_without_a_transfer_to_a_relative() -> None:
    assert detect_signals("Necesito ver unos datos para mi hermano").merged(MODEL_THIRD_PARTY).third_party_admission


def test_sending_something_other_than_money_to_a_relative_keeps_the_model_flag() -> None:
    assert detect_signals("Manda o extrato pra minha mãe").merged(MODEL_THIRD_PARTY).third_party_admission is True
