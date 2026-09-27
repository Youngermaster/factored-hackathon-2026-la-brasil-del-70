"""Finish a reply: render the template, verify it, and optionally let the language model phrase it.

Phrasing is off by default (``WORKFLOW_LLM_PHRASING``). When on, the model receives the template text as its facts
and the rendered clause texts (a credit reply adds only the outcome code, the rendered reasons, and the disclaimer,
never the profile or the estimate), and its draft must pass the grounding verifier with the same evidence; any
violation or gateway failure keeps the template, and the violation kinds go into the execution record.
"""

from bank_agent.application.engine.context import TurnContext
from bank_agent.application.engine.llm import PHRASE_RESPONSE, text
from bank_agent.application.engine.render import MAX_TEXT, Renderer, RenderInput
from bank_agent.application.engine.reply import Reply
from bank_agent.application.grounding.draft import ResponseDraft
from bank_agent.domain.conversation import AssistantResponse
from bank_agent.domain.execution_record import GroundingReport
from bank_agent.domain.intelligence import PromptValue
from bank_agent.domain.locale import Language

_KINDS = (
    ("eligibility", "eligibility_result"),
    ("confirm", "confirm_request"),
    ("offer", "confirm_request"),
    ("created", "action_result"),
    ("blocked", "action_result"),
    ("clarify", "clarify"),
    ("ask", "clarify"),
    ("escalated", "handoff"),
    ("out_of_scope", "abstain"),
    ("denied", "abstain"),
    ("refused", "abstain"),
    ("abstain", "abstain"),
)


def response_kind(template: str) -> str:
    return next((kind for marker, kind in _KINDS if marker in template), "answer")


def render_input(ctx: TurnContext) -> RenderInput:
    bound = ctx.bound().refs
    return RenderInput(
        language=ctx.language,
        locale=ctx.locale,
        jurisdiction=ctx.customer.country,
        workflow=None if ctx.at_router else ctx.workflow,
        currency=ctx.currency,
        bound=bound,
        actions=tuple(ctx.recorder.verified_actions),
    )


async def finish_reply(ctx: TurnContext, renderer: Renderer, reply: Reply) -> AssistantResponse:
    rendered = renderer.render(reply, render_input(ctx))
    ctx.recorder.citations.extend(rendered.citations)
    kinds = [violation.kind.value for violation in rendered.violations]
    if kinds:
        ctx.recorder.intervention("grounding_violation")
    response = rendered.response
    used = False
    phrasing = ctx.settings.llm_phrasing and not reply.bilingual and ctx.language in (Language.ES, Language.PT)
    if phrasing:
        variables: dict[str, PromptValue] = {
            "workflow": "router" if ctx.at_router else ctx.workflow.value,
            "response_kind": response_kind(reply.template),
            "facts": [line for line in rendered.response.text.split("\n") if line.strip()][:20],
            "clause_texts": list(rendered.clause_texts),
            "customer_message": ctx.text,
            "dialect_hint": ctx.locale.value,
        }
        credit = reply.credit
        if credit is not None and credit.outcome is not None:
            # Only the outcome code, the rendered reasons, and the disclaimer: never the profile or the estimate.
            variables["eligibility_outcome"] = credit.outcome
            variables["eligibility_reasons"] = list(credit.reasons)
            if credit.disclaimer is not None:
                variables["disclaimer"] = credit.disclaimer
        drafted = await text(ctx, PHRASE_RESPONSE, variables)
        if drafted and drafted.strip():
            draft = ResponseDraft(text=drafted.strip()[:MAX_TEXT], citations=rendered.citations)
            violations = ctx.services.verifier.verify(draft, rendered.context)
            if violations:
                ctx.recorder.intervention("phrasing_rejected")
                kinds.extend(violation.kind.value for violation in violations)
            else:
                response = response.evolve(text=draft.text)
                used = True
    ctx.recorder.grounding = GroundingReport(
        llm_phrasing_used=used, template_id=reply.template, violations=tuple(dict.fromkeys(kinds))
    )
    return response
