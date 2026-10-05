"""The bank's own dispute words are not a legal or regulator mention (QA finding DSP-01).

"Reclamación" is the word the bot itself uses for a dispute. The model read it as a formal complaint body and the
signal escalated every dispute status question and intake. When the text uses the bank's dispute words with no legal
or authority hint, the model's legal flag is dropped; the keyword detector still escalates on its own.
"""

import pytest

from bank_agent.application.engine.signals import detect_signals
from bank_agent.domain.llm_outputs import EscalationSignals

MODEL_LEGAL = EscalationSignals(
    legal_or_regulator_mention=True, distress=False, human_requested=False, third_party_admission=False
)


@pytest.mark.parametrize(
    "text",
    [
        "¿Cómo va mi reclamación?",
        "Quiero presentar una reclamación por un cobro que no hice",
        "Desconozco un cargo y quiero una aclaración",
        "Como está a minha contestação?",
        "Quero abrir uma reclamação",
        "Não reconheço essa compra, quero contestar",
    ],
)
def test_bank_dispute_wording_drops_the_model_legal_flag(text: str) -> None:
    assert detect_signals(text).merged(MODEL_LEGAL).legal_or_regulator_mention is False


@pytest.mark.parametrize(
    "text",
    [
        "Voy a poner una reclamación ante la Superintendencia",
        "Voy a poner una queja formal ante la autoridad",
        "Si no me resuelven la reclamación voy a ir a la SIC",
        "vou reclamar no Procon",
        "Vou registrar no Reclame Aqui essa reclamação",
        "Quero levar a contestação para a ouvidoria",
    ],
)
def test_dispute_wording_with_an_authority_still_escalates_as_legal(text: str) -> None:
    assert detect_signals(text).merged(MODEL_LEGAL).legal_or_regulator_mention is True


def test_model_legal_flag_still_counts_without_dispute_wording() -> None:
    assert detect_signals("Esto ya lo verá mi primo").merged(MODEL_LEGAL).legal_or_regulator_mention is True


@pytest.mark.parametrize(
    "text",
    ["Voy a acudir a la Superintendencia", "vou reclamar no Procon", "Lo voy a llevar a la autoridad competente"],
)
def test_keyword_legal_detection_is_unchanged_by_the_guard(text: str) -> None:
    assert detect_signals(text).legal_or_regulator_mention is True
