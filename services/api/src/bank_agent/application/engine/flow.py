"""Routing and the handler loop: pending questions, router dispatch, workflow entry and switches, and the chain
of state handlers within one turn, each transition checked against the definition."""

from dataclasses import replace

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.data import PendingSwitch, PendingWorkflowChoice
from bank_agent.application.engine.decide import clarification_left, evaluate
from bank_agent.application.engine.definition import StateKind
from bank_agent.application.engine.gate import pause
from bank_agent.application.engine.registry import WorkflowRegistry
from bank_agent.application.engine.reply import Param, Reply
from bank_agent.application.engine.router import Route, RouteKind, dispatch
from bank_agent.application.engine.shared import (
    escalate,
    escalate_decision,
    greeting,
    human_requested,
    informational,
    out_of_scope,
    step_up,
)
from bank_agent.application.engine.templates.labels import PENDING, TOPICS
from bank_agent.application.understanding.answers import YesNo, parse_choice, parse_yes_no
from bank_agent.application.understanding.text import fold
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import AuthenticationError, StepUpRequiredError, ToolError, ToolNotAllowedError
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Outcome, WorkflowId

SHARED_REPLIES = frozenset({RouteKind.OUT_OF_SCOPE, RouteKind.INFORMATIONAL})


def _label(table: dict[WorkflowId, dict[Language, str]], workflow: WorkflowId, language: Language) -> str:
    return table[workflow][Language.ES if language is Language.EN else language]


def enter(ctx: TurnContext, registry: WorkflowRegistry, target: WorkflowId, *, switch: bool) -> None:
    """Start ``target`` at its entry state, keeping only verified facts (and a chosen card) from before."""
    if switch and not ctx.at_router:
        ctx.workflow_before = ctx.definition.ref
    ctx.definition = registry.definition(target)
    ctx.at_router = False
    ctx.state = ctx.definition.entry_state
    ctx.flow = {}
    ctx.clarifications_used = 0
    ctx.turns_used = 0
    ctx.engine = ctx.engine.evolve(pending_switch=None, pending_choice=None, resume_state=None)


async def run_handlers(ctx: TurnContext) -> Step:
    steps = 0
    while True:
        spec = ctx.definition.spec(ctx.state)
        ctx.tools.allow(spec.allowed_tools)
        try:
            step = await spec.handler(ctx)
        except AuthenticationError:
            return pause(ctx)
        except StepUpRequiredError:
            return step_up(ctx, ctx.state)
        except ToolNotAllowedError:
            return escalate(ctx, EscalationReasonCode.OTHER, "tool_not_allowed_in_state")
        except ToolError as error:
            decision = evaluate(ctx, tool_failures=1)
            if decision.decisive_rule_ids:
                return escalate_decision(ctx, decision)
            return escalate(ctx, EscalationReasonCode.TOOL_FAILURE, error.code, decision=decision)
        ctx.definition.check_transition(ctx.state, step.next_state)
        ctx.state = step.next_state
        ctx.reprompt = False
        if step.reply is not None:
            return step
        steps += 1
        if steps > ctx.settings.max_steps:
            return escalate(ctx, EscalationReasonCode.OTHER, "handler_step_limit")


async def apply_route(ctx: TurnContext, registry: WorkflowRegistry, route: Route) -> Step:
    kind = route.kind
    if kind is RouteKind.OUT_OF_SCOPE:
        return out_of_scope(ctx)
    if kind is RouteKind.INFORMATIONAL:
        return informational(ctx)
    if kind is RouteKind.HUMAN:
        return human_requested(ctx)
    if kind is RouteKind.GREETING:
        return greeting(ctx)
    if kind is RouteKind.CLARIFY_WORKFLOW:
        return clarify_workflow(ctx, route.options)
    if kind is RouteKind.CONFIRM_SWITCH and route.target is not None:
        return confirm_switch(ctx, route.target)
    if kind in (RouteKind.START, RouteKind.SWITCH) and route.target is not None:
        enter(ctx, registry, route.target, switch=kind is RouteKind.SWITCH)
    return await run_handlers(ctx)


def clarify_workflow(ctx: TurnContext, options: tuple[WorkflowId, ...]) -> Step:
    if not clarification_left(ctx):
        decision = evaluate(ctx, clarification_attempts=ctx.clarifications_used)
        return escalate_decision(ctx, decision)
    ctx.clarifications_used += 1
    ctx.engine = ctx.engine.evolve(pending_choice=PendingWorkflowChoice(options=options, text=ctx.text))
    params: dict[str, Param] = {
        "first": _label(TOPICS, options[0], ctx.language),
        "second": _label(TOPICS, options[1], ctx.language),
    }
    return Step(ctx.state, Reply(template="common.clarify_workflow", params=params), Outcome.CLARIFIED)


def confirm_switch(ctx: TurnContext, target: WorkflowId) -> Step:
    intent = ctx.prediction.intent if ctx.prediction is not None else None
    if intent is None:
        return greeting(ctx, clarify=True)
    ctx.engine = ctx.engine.evolve(pending_switch=PendingSwitch(target=target, intent=intent, text=ctx.text))
    params: dict[str, Param] = {
        "pending": _label(PENDING, ctx.workflow, ctx.language),
        "target": _label(TOPICS, target, ctx.language),
    }
    return Step(ctx.state, Reply(template="common.switch_confirm", params=params), Outcome.CLARIFIED)


async def answer_pending(ctx: TurnContext, registry: WorkflowRegistry) -> Step | None:
    """Answers to the engine's own questions: which workflow, and whether to switch."""
    choice = ctx.engine.pending_choice
    if choice is not None:
        ctx.engine = ctx.engine.evolve(pending_choice=None)
        picked = _pick_workflow(ctx, registry, choice.options)
        if picked is None:
            return None
        ctx.text = UntrustedText(choice.text)
        enter(ctx, registry, picked, switch=not ctx.at_router)
        return await run_handlers(ctx)
    pending = ctx.engine.pending_switch
    if pending is None:
        return None
    answer = parse_yes_no(ctx.text)
    if answer is YesNo.UNCLEAR:
        return confirm_switch(ctx, pending.target)
    ctx.engine = ctx.engine.evolve(pending_switch=None)
    if answer is YesNo.YES:
        ctx.text = UntrustedText(pending.text)
        enter(ctx, registry, pending.target, switch=True)
        return await run_handlers(ctx)
    ctx.reprompt = True
    step = await run_handlers(ctx)
    params: dict[str, Param] = {"pending": _label(PENDING, ctx.workflow, ctx.language)}
    if step.reply is not None and step.reply.prefix is None:
        step = Step(step.next_state, _with_prefix(step.reply, "common.switch_declined", params), step.outcome)
    return step


def _with_prefix(reply: Reply, prefix: str, params: dict[str, Param]) -> Reply:
    return replace(reply, prefix=prefix, params={**params, **reply.params})


def _pick_workflow(ctx: TurnContext, registry: WorkflowRegistry, options: tuple[WorkflowId, ...]) -> WorkflowId | None:
    def matches(folded: str, workflow: WorkflowId) -> bool:
        words = [w for w in fold(_label(TOPICS, workflow, ctx.language)).split() if len(w) > 3]
        return any(word in folded for word in words)

    index = parse_choice(ctx.text, options, matches)
    if index is not None:
        return options[index]
    owner = registry.owner(ctx.services.router.route(ctx.text, ctx.language).intent)
    return owner if owner in options else None


async def route_and_run(ctx: TurnContext, registry: WorkflowRegistry) -> Step:
    pending = await answer_pending(ctx, registry)
    if pending is not None:
        return pending
    spec = ctx.definition.spec(ctx.state)
    current = None if ctx.at_router else ctx.workflow
    if ctx.at_router or spec.kind is StateKind.ACCEPTS_REQUEST:
        prediction = ctx.services.router.route(ctx.text, ctx.language)
        ctx.prediction = prediction
        ctx.recorder.model(prediction.model)
        route = dispatch(prediction, registry, current=current, mid_flow=spec.mid_flow)
        return await apply_route(ctx, registry, route)
    step = await run_handlers(ctx)
    if not step.unanswered:
        return step
    prediction = ctx.services.router.route(ctx.text, ctx.language)
    ctx.prediction = prediction
    ctx.recorder.model(prediction.model)
    route = dispatch(prediction, registry, current=current, mid_flow=True)
    if route.kind in (RouteKind.CONFIRM_SWITCH, RouteKind.SWITCH) and route.target is not None:
        return confirm_switch(ctx, route.target)
    if route.kind is RouteKind.HUMAN:
        return human_requested(ctx)
    if route.kind in SHARED_REPLIES:
        shared = await apply_route(ctx, registry, route)
        return Step(ctx.state, shared.reply, shared.outcome)
    return step
