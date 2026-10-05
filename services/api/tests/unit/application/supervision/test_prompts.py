"""The supervision prompt list follows the engine's prompt constants and the three ``WORKFLOW_LLM_*`` flags."""

from bank_agent.application.engine import llm
from bank_agent.application.supervision.prompts import ENGINE_PROMPTS, prompt_uses
from bank_agent.domain.intelligence import PromptRef

REGISTERED = (
    *ENGINE_PROMPTS,
    PromptRef.model_validate("detect_escalation_signals@1"),
    PromptRef.model_validate("classify_intent_fallback@1"),
)


def test_every_prompt_constant_of_the_engine_is_listed() -> None:
    constants = {value for value in vars(llm).values() if isinstance(value, PromptRef)}
    assert constants == set(ENGINE_PROMPTS)


def test_the_flags_decide_which_engine_prompts_are_active() -> None:
    uses = prompt_uses(REGISTERED, model_configured=True, understanding=True, phrasing=False, handoff_summary=True)
    active = {str(use.prompt) for use in uses if use.active}
    assert active == {
        "extract_account_inquiry_slots@1",
        "extract_card_support_slots@1",
        "extract_dispute_slots@1",
        "extract_credit_slots@1",
        "detect_escalation_signals@2",
        "summarize_for_handoff@1",
    }
    assert [str(use.prompt) for use in uses if use.purpose == "not_called_by_engine"] == [
        "classify_intent_fallback@1",
        "detect_escalation_signals@1",
    ]


def test_without_a_configured_model_no_prompt_is_active() -> None:
    uses = prompt_uses(REGISTERED, model_configured=False, understanding=True, phrasing=True, handoff_summary=True)
    assert not any(use.active for use in uses)
    assert len(uses) == len(REGISTERED)
