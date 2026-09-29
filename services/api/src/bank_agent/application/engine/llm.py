"""Calls to the language model gateway from the engine, always with a deterministic fallback.

Every call names its prompt by id and version, passes only the variables the prompt declares (customer text as
``UntrustedText``), and carries the session's first name as a sensitive term so the redaction decorator masks it.
Any ``LlmError`` is recorded (status ``fallback`` with the error code) and returns ``None``; the caller then uses
its deterministic path. In template-only mode (degradation level L2) no call is attempted: the skip is recorded the
same way with the code ``degraded_template_only``. The model's output is understanding only: it never names a
state, a tool, or a customer.
"""

from collections.abc import Mapping

from pydantic import BaseModel

from bank_agent.application.engine.context import TurnContext
from bank_agent.domain.errors import LlmError
from bank_agent.domain.intelligence import LlmCallContext, PromptRef, PromptValue

EXTRACT_DISPUTE = PromptRef(prompt_id="extract_dispute_slots", version=1)
EXTRACT_CARD = PromptRef(prompt_id="extract_card_support_slots", version=1)
EXTRACT_ACCOUNT = PromptRef(prompt_id="extract_account_inquiry_slots", version=1)
EXTRACT_CREDIT = PromptRef(prompt_id="extract_credit_slots", version=1)
DETECT_SIGNALS = PromptRef(prompt_id="detect_escalation_signals", version=1)
PHRASE_RESPONSE = PromptRef(prompt_id="phrase_response", version=1)
SUMMARIZE_HANDOFF = PromptRef(prompt_id="summarize_for_handoff", version=1)
MIN_SENSITIVE = 2
TEMPLATE_ONLY = "degraded_template_only"


def skipped(ctx: TurnContext, prompt: PromptRef) -> bool:
    """True, and recorded, when the degradation ladder says no model call may be attempted this turn."""
    if not ctx.degradation.template_only:
        return False
    ctx.recorder.llm_skipped(prompt, TEMPLATE_ONLY)
    return True


def call_context(ctx: TurnContext) -> LlmCallContext:
    name = ctx.customer.first_name.strip()
    return LlmCallContext(
        lineage_id=ctx.conversation.lineage_id,
        conversation_id=ctx.conversation.conversation_id,
        turn_id=ctx.turn_id,
        sensitive_terms=(name,) if len(name) >= MIN_SENSITIVE else (),
    )


async def structured[OutputT: BaseModel](
    ctx: TurnContext, prompt: PromptRef, variables: Mapping[str, PromptValue], output_model: type[OutputT]
) -> OutputT | None:
    """The validated output, or ``None`` when understanding by model is off or the gateway fails."""
    if not ctx.settings.llm_understanding or skipped(ctx, prompt):
        return None
    try:
        generation = await ctx.services.llm.generate_structured(
            prompt,
            variables,
            output_model,
            language=ctx.language,
            max_output_tokens=ctx.settings.llm_max_output_tokens,
            temperature=0.0,
            call_context=call_context(ctx),
        )
    except LlmError as error:
        ctx.recorder.llm_failure(prompt, error)
        return None
    ctx.recorder.llm_success(generation)
    return generation.value


async def text(ctx: TurnContext, prompt: PromptRef, variables: Mapping[str, PromptValue]) -> str | None:
    if skipped(ctx, prompt):
        return None
    try:
        generation = await ctx.services.llm.generate_text(
            prompt,
            variables,
            language=ctx.language,
            max_output_tokens=ctx.settings.llm_max_output_tokens,
            temperature=0.0,
            call_context=call_context(ctx),
        )
    except LlmError as error:
        ctx.recorder.llm_failure(prompt, error)
        return None
    ctx.recorder.llm_success(generation)
    return generation.text
