"""The per-session assessment limit: repeated synthetic eligibility assessments reach a person, never a map of rules."""

from datetime import timedelta

import pytest

from bank_agent_api import ApiBackend, ApiClient

QUESTIONS = {
    "es": "Quiero saber si califico para un préstamo personal de 50 mil pesos a 24 meses",
    "pt": "Quero saber se sou elegível para um empréstimo pessoal de 50 mil pesos em 24 meses",
}


@pytest.mark.parametrize(("persona", "language"), [("persona-mx", "es"), ("persona-pt", "pt")])
async def test_past_the_limit_the_request_goes_to_a_person_in_every_conversation(
    api_backend: ApiBackend, monkeypatch: pytest.MonkeyPatch, persona: str, language: str
) -> None:
    monkeypatch.setenv("WORKFLOW_MAX_ELIGIBILITY_ASSESSMENTS", "1")
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        await client.login(persona, language=language)
        first = await client.say(await client.open_conversation(), QUESTIONS[language])
        second = await client.say(await client.open_conversation(), QUESTIONS[language])
    assert first.status_code == second.status_code == 200
    assert first.json()["message"]["eligibility"] is not None
    body = second.json()
    assert (body["state"], body["outcome"]) == ("ESCALATED", "escalated")
    assert body["message"]["eligibility"] is None
    assert body["message"]["escalation"]["handoff_id"]


async def test_the_limit_counts_only_the_window(api_backend: ApiBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKFLOW_MAX_ELIGIBILITY_ASSESSMENTS", "1")
    harness = api_backend.build()
    async with ApiClient(harness.app) as client:
        await client.login("persona-mx", language="es")
        await client.say(await client.open_conversation(), QUESTIONS["es"])
        harness.clock.advance(timedelta(minutes=harness.settings.workflow.eligibility_assessment_window_minutes + 1))
        await client.login("persona-mx", language="es")
        again = await client.say(await client.open_conversation(), QUESTIONS["es"])
    assert again.json()["message"]["eligibility"] is not None
