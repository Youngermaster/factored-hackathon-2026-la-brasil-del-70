"""Version 1.4.0 of the scenario contract: scripted fallback turns for simulated scenarios and template families."""

from typing import Any

import pytest
from pydantic import ValidationError

from bank_evals.scenarios.model import Scenario

SIMULATED: dict[str, Any] = {
    "id": "card-ambiguous-es-001",
    "split": "dev",
    "language": "es",
    "dialect": "es-AR",
    "category": "ambiguous",
    "persona_ref": "crd-ar",
    "goal": "Ask about the card without saying which one.",
    "mode": "simulated",
    "simulator_instructions": "Ask about your card; say which one only when asked.",
    "scripted_fallback": [{"text": "¿Cómo está mi tarjeta?"}, {"text": "la de débito"}],
    "template_family": "card.ambiguous.which-card",
    "workflow": "card_support",
    "expected_outcome": "resolved",
    "in_scope": True,
    "provenance": "team_generated",
}


def test_a_simulated_scenario_carries_fallback_turns_and_its_family() -> None:
    scenario = Scenario.model_validate(SIMULATED)
    assert [turn.text for turn in scenario.scripted_fallback] == ["¿Cómo está mi tarjeta?", "la de débito"]
    assert scenario.template_family == "card.ambiguous.which-card"
    assert scenario.schema_version == "1.4.0"


def test_only_a_simulated_scenario_has_fallback_turns() -> None:
    scripted = {**SIMULATED, "mode": "scripted", "simulator_instructions": None, "turns": [{"text": "hola"}]}
    with pytest.raises(ValidationError, match="only a simulated scenario"):
        Scenario.model_validate(scripted)


def test_a_1_3_document_cannot_claim_the_new_fields() -> None:
    with pytest.raises(ValidationError):
        Scenario.model_validate({**SIMULATED, "schema_version": "1.3.0"})
    old = {k: v for k, v in SIMULATED.items() if k not in {"scripted_fallback", "template_family"}}
    assert Scenario.model_validate({**old, "schema_version": "1.3.0"}).scripted_fallback == ()
