"""The optional model summary of a handoff (``WORKFLOW_LLM_HANDOFF_SUMMARY``, off by default).

``summarize_for_handoff`` receives the numbered verified facts, the actions with their verification status, the
escalation reason, and the open questions. Its draft replaces the deterministic summary only when every cited fact
id was passed in, every figure it states appears in a cited fact, and it claims no action that was not executed and
verified. Otherwise, or on any gateway error, the deterministic summary stays and the rejection is recorded.
"""

from bank_agent.application.engine.context import TurnContext
from bank_agent.application.engine.handoff import validate_handoff
from bank_agent.application.engine.llm import SUMMARIZE_HANDOFF, call_context, skipped
from bank_agent.application.grounding.lexicon import ClaimedAction, claimed_actions
from bank_agent.application.grounding.numbers import Figure, extract_figures, fold_same_length
from bank_agent.domain.errors import LlmError
from bank_agent.domain.intelligence import PromptValue
from bank_agent.domain.llm_outputs import HandoffSummaryDraft


def _signature(figure: Figure) -> tuple[object, ...]:
    return (figure.kind, figure.values, figure.day, figure.month_day, figure.digits)


def grounded(draft: HandoffSummaryDraft, facts: dict[str, str], verified: set[str]) -> bool:
    if not set(draft.cited_fact_ids) <= set(facts):
        return False
    allowed = {_signature(f) for fact_id in draft.cited_fact_ids for f in extract_figures(facts[fact_id])}
    if any(_signature(figure) not in allowed for figure in extract_figures(draft.summary)):
        return False
    claims = {action for action, _, _ in claimed_actions(fold_same_length(draft.summary))}
    return all(claim is not ClaimedAction.UNSUPPORTED and claim.value in verified for claim in claims)


async def refine_summary(ctx: TurnContext) -> None:
    handoff = ctx.handoff
    if handoff is None or not ctx.settings.llm_handoff_summary or skipped(ctx, SUMMARIZE_HANDOFF):
        return
    facts = {f"F{index}": fact.fact for index, fact in enumerate(handoff.verified_facts, 1)}
    verified = {item.action.value for item in handoff.actions_taken if item.verification.value == "verified"}
    variables: dict[str, PromptValue] = {
        "request": ctx.text,
        "verified_facts": [f"{fact_id} {text}" for fact_id, text in facts.items()],
        "actions_taken": [f"{a.action.value}: {a.status.value}, {a.verification.value}" for a in handoff.actions_taken],
        "escalation_reason": handoff.escalation_reason.code.value,
        "open_questions": list(handoff.open_questions),
    }
    try:
        generation = await ctx.services.llm.generate_structured(
            SUMMARIZE_HANDOFF,
            variables,
            HandoffSummaryDraft,
            language=handoff.language,
            max_output_tokens=ctx.settings.llm_max_output_tokens,
            temperature=0.0,
            call_context=call_context(ctx),
        )
    except LlmError as error:
        ctx.recorder.llm_failure(SUMMARIZE_HANDOFF, error)
        return
    ctx.recorder.llm_success(generation)
    if not facts or not grounded(generation.value, facts, verified):
        ctx.recorder.intervention("handoff_summary_rejected")
        return
    refined = handoff.evolve(request=handoff.request.evolve(summary=generation.value.summary))
    validate_handoff(refined)
    ctx.handoff = refined
