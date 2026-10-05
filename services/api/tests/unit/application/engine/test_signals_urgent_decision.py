"""Urgency about a credit decision is not distress by itself (QA finding CRE-16).

"Apruébame el préstamo personal ya, ándale, lo necesito hoy" was escalated as distress with the 4-hour priority,
because the model read the urgency as hardship, instead of getting the CRE-ALL-3 abstention. With an approval
demand and urgency words, the model's distress flag is dropped; keyword distress still escalates.
"""

import pytest

from bank_agent.application.engine.signals import detect_signals
from bank_agent.domain.llm_outputs import EscalationSignals

MODEL_DISTRESS = EscalationSignals(
    legal_or_regulator_mention=False, distress=True, human_requested=False, third_party_admission=False
)


@pytest.mark.parametrize(
    "text",
    [
        "Apruébame el préstamo personal ya, ándale, lo necesito hoy",
        "Aprueba mi crédito urgente",
        "Aprova meu empréstimo, preciso hoje",
        "Me aprova o crédito agora",
    ],
)
def test_an_urgent_approval_demand_drops_the_model_distress_flag(text: str) -> None:
    assert detect_signals(text).merged(MODEL_DISTRESS).distress is False


@pytest.mark.parametrize(
    "text",
    [
        "Apruébame el préstamo ya, no tengo para comer",
        "Aprova meu empréstimo agora, estou desesperado",
        "Aprueba mi crédito hoy, mi hijo está en el hospital",
    ],
)
def test_an_approval_demand_with_hardship_still_escalates_as_distress(text: str) -> None:
    assert detect_signals(text).merged(MODEL_DISTRESS).distress is True


@pytest.mark.parametrize("text", ["Necesito el dinero hoy, la estoy pasando muy mal", "Apruébame el préstamo"])
def test_the_model_distress_flag_counts_without_an_urgent_approval_demand(text: str) -> None:
    assert detect_signals(text).merged(MODEL_DISTRESS).distress is True
