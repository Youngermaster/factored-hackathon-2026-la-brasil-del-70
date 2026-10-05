"""The prompt versions the engine calls, what for, and whether the current feature flags let each one run.

The engine's prompt constants live in ``application/engine/llm.py``; this module maps each one to the
``WORKFLOW_LLM_*`` flag that gates it, so the list the supervision view shows cannot drift from what the engine calls.
A registered prompt the engine never calls (an offline tool's prompt, an older version) is listed as such. Without a
configured model nothing is active: every call would be refused and the deterministic path answers.
"""

from collections.abc import Iterable, Mapping
from typing import Final

from bank_agent.application.engine.llm import (
    DETECT_SIGNALS,
    EXTRACT_ACCOUNT,
    EXTRACT_CARD,
    EXTRACT_CREDIT,
    EXTRACT_DISPUTE,
    PHRASE_RESPONSE,
    SUMMARIZE_HANDOFF,
)
from bank_agent.domain.intelligence import PromptRef
from bank_agent.domain.model_inventory import PromptPurpose, PromptUse

ENGINE_PROMPTS: Final[Mapping[PromptRef, PromptPurpose]] = {
    EXTRACT_ACCOUNT: "understanding",
    EXTRACT_CARD: "understanding",
    EXTRACT_DISPUTE: "understanding",
    EXTRACT_CREDIT: "understanding",
    DETECT_SIGNALS: "understanding",
    PHRASE_RESPONSE: "phrasing",
    SUMMARIZE_HANDOFF: "handoff_summary",
}
"""Every prompt the workflow engine calls, by the feature flag that gates it."""


def prompt_uses(
    registered: Iterable[PromptRef],
    *,
    model_configured: bool,
    understanding: bool,
    phrasing: bool,
    handoff_summary: bool,
) -> tuple[PromptUse, ...]:
    """The engine's prompts first (in the order above), then every other registered version, sorted."""
    flags: Mapping[PromptPurpose, bool] = {
        "understanding": model_configured and understanding,
        "phrasing": model_configured and phrasing,
        "handoff_summary": model_configured and handoff_summary,
        "not_called_by_engine": False,
    }
    engine = [PromptUse(prompt=ref, purpose=purpose, active=flags[purpose]) for ref, purpose in ENGINE_PROMPTS.items()]
    others = sorted(
        {ref for ref in registered if ref not in ENGINE_PROMPTS}, key=lambda ref: (ref.prompt_id, ref.version)
    )
    return (
        *engine,
        *(PromptUse(prompt=ref, purpose="not_called_by_engine", active=False) for ref in others),
    )
