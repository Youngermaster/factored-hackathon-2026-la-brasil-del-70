"""The scripted client of the smoke suite (``--llm fake``): no model, deterministic, for CI.

It answers the escalation signals with no signal, refuses the understanding, phrasing, and summary prompts (so P
takes its deterministic fallbacks, as with no provider), makes B1 ask a clarifying question at every step, refuses
the simulated user (so simulated scenarios play their scripted fallback), and gives the judge a fixed rating. It
checks the wiring of every system and driver; its numbers mean nothing and are labeled ``fake/scripted``.
"""

from __future__ import annotations

from typing import Final

from pydantic import JsonValue

from bank_agent.domain.errors import LlmProviderRejectedError
from bank_agent.domain.intelligence import PromptRef
from bank_agent.testing.fake_llm import FakeLLM, ScriptedError, ScriptedResponse

FAKE_LABEL: Final = "fake/scripted (smoke, no model)"
REFUSED: Final = (
    "extract_dispute_slots",
    "extract_account_inquiry_slots",
    "extract_card_support_slots",
    "extract_credit_slots",
    "classify_intent_fallback",
    "phrase_response",
    "summarize_for_handoff",
    "simulate_customer",
    "translate_to_portuguese",
)
NO_SIGNALS: Final[dict[str, JsonValue]] = {
    "legal_or_regulator_mention": False,
    "distress": False,
    "human_requested": False,
    "third_party_admission": False,
}
B1_STEP: Final[dict[str, JsonValue]] = {
    "action": "reply",
    "tool": None,
    "arguments": {},
    "reply": "¿Me das más detalles, por favor?",
    "outcome": "clarified",
}
RATING: Final[dict[str, JsonValue]] = {
    "language_correct": True,
    "tone": 4,
    "clarity": 4,
    "politeness": 4,
    "language_quality": 4,
}


def smoke_llm() -> FakeLLM:
    fake = FakeLLM()
    for prompt_id in REFUSED:
        fake.script(PromptRef(prompt_id=prompt_id, version=1), ScriptedError(LlmProviderRejectedError))
    fake.script(PromptRef(prompt_id="detect_escalation_signals", version=1), ScriptedResponse(output=NO_SIGNALS))
    fake.script(PromptRef(prompt_id="naive_agent_step", version=1), ScriptedResponse(output=B1_STEP))
    fake.script(PromptRef(prompt_id="judge_transcript", version=1), ScriptedResponse(output=RATING))
    return fake
