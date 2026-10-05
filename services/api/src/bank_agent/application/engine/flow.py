"""Routing and the handler loop: pending questions, router dispatch, workflow entry and switches, and the chain
of state handlers within one turn, each transition checked against the definition."""

import re
from dataclasses import replace

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.data import PendingSwitch, PendingWorkflowChoice
from bank_agent.application.engine.decide import clarification_left, evaluate
from bank_agent.application.engine.definition import StateKind, StateSpec
from bank_agent.application.engine.gate import pause
from bank_agent.application.engine.observed import run_state
from bank_agent.application.engine.registry import WorkflowRegistry
from bank_agent.application.engine.reply import Param, Reply
from bank_agent.application.engine.router import Route, RouteKind, dispatch
from bank_agent.application.engine.shared import (
    abstain_unsupported,
    blocking_step,
    escalate,
    escalate_decision,
    greeting,
    human_requested,
    informational,
    off_topic,
    out_of_scope,
    step_up,
)
from bank_agent.application.engine.signals import plain_answer
from bank_agent.application.engine.templates.labels import PENDING, TOPICS
from bank_agent.application.understanding.answers import YesNo, parse_choice, parse_yes_no
from bank_agent.application.understanding.scope import Scope, classify_scope
from bank_agent.application.understanding.text import fold
from bank_agent.domain.access import AuthLevel
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.errors import (
    AuthenticationError,
    StepUpRequiredError,
    ToolError,
    ToolNotAllowedError,
    WorkflowTransitionError,
)
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.intelligence import IntentPrediction, ModelComponent, ModelRef
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Outcome, WorkflowId

SHARED_REPLIES = frozenset({RouteKind.OUT_OF_SCOPE, RouteKind.INFORMATIONAL})
UNSURE_ROUTES = frozenset({RouteKind.CLARIFY_WORKFLOW, RouteKind.GREETING})
FOLLOW_UP_MODEL = ModelRef(component=ModelComponent.ROUTER, name="context_follow_up", version="1")
"""Recorded when a context follow-up, not the router, gave the turn's intent."""


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
    ctx.engine = ctx.engine.evolve(pending_switch=None, pending_choice=None, resume_state=None, step_up_state=None)


def auth_gate(ctx: TurnContext, spec: StateSpec) -> Step | None:
    """Before a handler reads anything, the kernel checks the authentication its binding state needs (a higher
    risk tier raises it to step-up); a deny or a step-up request stops here."""
    if ctx.services.policy.pack.bindings.binding(ctx.workflow, spec.policy_state).auth is AuthLevel.NONE:
        return None
    decision = evaluate(ctx, policy_state=spec.policy_state)
    auth = any(rule_id.startswith("AUTH.") for rule_id in decision.decisive_rule_ids)
    if auth and decision.kind in (DecisionKind.DENY, DecisionKind.REQUIRE_STEP_UP):
        return blocking_step(ctx, decision, state=ctx.state)
    return None


async def run_handlers(ctx: TurnContext) -> Step:
    steps = 0
    while True:
        spec = ctx.definition.spec(ctx.state)
        stopped = auth_gate(ctx, spec)
        if stopped is not None:
            return stopped
        ctx.tools.allow(spec.allowed_tools)
        asked_again = ctx.reprompt
        try:
            step = await run_state(ctx, spec)
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
        if asked_again:
            ctx.reprompt = False
        if step.reply is not None:
            return step
        steps += 1
        if steps > ctx.settings.max_steps:
            return escalate(ctx, EscalationReasonCode.OTHER, "handler_step_limit")


async def apply_route(ctx: TurnContext, registry: WorkflowRegistry, route: Route) -> Step:
    kind = route.kind
    menu = ctx.settings.menu_template
    if menu is not None and kind in (RouteKind.GREETING, RouteKind.CLARIFY_WORKFLOW):
        return Step(ctx.state, Reply(template=menu, bilingual=True), Outcome.CLARIFIED)
    if kind is RouteKind.OUT_OF_SCOPE:
        return in_domain_unsupported(ctx, registry) or out_of_scope(ctx)
    if kind is RouteKind.INFORMATIONAL:
        return await informational(ctx)
    if kind is RouteKind.HUMAN:
        return human_requested(ctx)
    if kind is RouteKind.GREETING:
        return outside_banking(ctx) or greeting(ctx)
    if kind is RouteKind.CLARIFY_WORKFLOW:
        # A request an enabled workflow recognizes as its own unsupported request (a transfer) is abstained with that
        # workflow's clauses instead of asking which workflow it belongs to (phase 14b, found on the dev split).
        return in_domain_unsupported(ctx, registry) or outside_banking(ctx) or clarify_workflow(ctx, route.options)
    if kind is RouteKind.CONFIRM_SWITCH and route.target is not None:
        return confirm_switch(ctx, route.target)
    if kind in (RouteKind.START, RouteKind.SWITCH) and route.target is not None:
        enter(ctx, registry, route.target, switch=kind is RouteKind.SWITCH)
    predicted = ctx.prediction.intent if ctx.prediction is not None else None
    if predicted is not None and predicted in ctx.definition.intents:
        ctx.engine = ctx.engine.evolve(intent=predicted)
    return await run_handlers(ctx)


def in_domain_unsupported(ctx: TurnContext, registry: WorkflowRegistry) -> Step | None:
    """A request no intent covers but that an enabled workflow recognizes as its own unsupported request (a
    transfer, a limit increase): abstained with that workflow's clauses. The current workflow is asked first. Outside
    a pending step the conversation moves to that workflow's ABSTAINED state; mid-flow the pending step is kept."""
    current = None if ctx.at_router else ctx.workflow
    order = ([current] if current is not None else []) + [w for w in ctx.enabled if w is not current]
    for workflow in order:
        recognize = registry.definition(workflow).unsupported
        request = recognize(ctx.text) if recognize is not None else None
        if request is None:
            continue
        if workflow is not current:
            if current is not None and ctx.definition.spec(ctx.state).mid_flow:
                kept = abstain_unsupported(ctx, request)
                return Step(ctx.state, kept.reply, kept.outcome)
            enter(ctx, registry, workflow, switch=current is not None)
        return abstain_unsupported(ctx, request)
    return None


def outside_banking(ctx: TurnContext) -> Step | None:
    """A message the router could not place that is not about banking at all (``scope:lexicon@1``): an unrelated
    topic gets the ``SCOPE-ALL-1`` abstention, a bank-side request the assistant never handles (personal data, tax
    advice) the generic out-of-scope answer. Greetings and plausible banking requests return ``None`` and keep the
    welcome or the clarifying question. Found before the pitch video ("¿Quién es mejor CR7 o Messi?" was asked
    "saldos o tarjetas")."""
    scope = classify_scope(ctx.text)
    if scope is Scope.OFF_TOPIC:
        return off_topic(ctx)
    if scope is Scope.SERVICE:
        return out_of_scope(ctx)
    return None


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


def confirm_switch(ctx: TurnContext, target: WorkflowId, *, pending: PendingSwitch | None = None) -> Step:
    """Ask whether to leave the current work for ``target``; ``pending`` asks the same question again, keeping the
    original request (an unclear answer must not replace it)."""
    if pending is None:
        intent = ctx.prediction.intent if ctx.prediction is not None else None
        if intent is None:
            return greeting(ctx, clarify=True)
        pending = PendingSwitch(target=target, intent=intent, text=ctx.text)
    ctx.engine = ctx.engine.evolve(pending_switch=pending)
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
        if picked is not None:
            ctx.text = UntrustedText(choice.text)
            enter(ctx, registry, picked, switch=not ctx.at_router)
            return await run_handlers(ctx)
        other = _answered_with_another_workflow(ctx, registry)
        if other is None:
            return None
        # The answer names a workflow we did not offer ("es sobre un cargo que no reconozco" after "saldos o
        # tarjetas"): start it with the original request and the answer together, so the details of the first
        # message (amount, merchant) are not lost (phase 14b, found on the dev split).
        ctx.text = UntrustedText(f"{choice.text}\n{ctx.text}")
        enter(ctx, registry, other, switch=not ctx.at_router)
        return await run_handlers(ctx)
    pending = ctx.engine.pending_switch
    if pending is None:
        return None
    answer = _switch_answer(ctx, registry, pending.target)
    if answer is YesNo.UNCLEAR:
        return confirm_switch(ctx, pending.target, pending=pending)
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


_CONTINUE_CURRENT = re.compile(
    r"\b(sigamos|seguimos|sigamos con|continuemos|continuamos|continuar|continua|volvamos|volvamos a|retomemos|"
    r"retomar|retoma|vamos continuar|vamos seguir|voltemos|voltar|prossigamos|prosseguir|prossiga)\b"
)


def _switch_answer(ctx: TurnContext, registry: WorkflowRegistry, target: WorkflowId) -> YesNo:
    """The answer to the engine's switch question. A message that asks to go on with the pending work ("Listo,
    sigamos con lo del cargo") is a no unless it routes to the offered workflow; a plain yes or no is read as is; a
    longer yes counts only when it routes to the offered workflow, and is asked again otherwise. Before QA finding
    DSP-08, the leading "listo" alone switched workflows and dropped the dispute."""
    answer = parse_yes_no(ctx.text)
    routes_to_target = answer is YesNo.YES and _routes_to(ctx, registry, target)
    if _CONTINUE_CURRENT.search(fold(ctx.text)):
        return YesNo.YES if routes_to_target else YesNo.NO
    if plain_answer(ctx.text):
        return answer
    if answer is YesNo.YES:
        return YesNo.YES if routes_to_target else YesNo.UNCLEAR
    return answer


def _routes_to(ctx: TurnContext, registry: WorkflowRegistry, target: WorkflowId) -> bool:
    return registry.owner(ctx.services.router.route(ctx.text, ctx.language).intent) is target


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


def _answered_with_another_workflow(ctx: TurnContext, registry: WorkflowRegistry) -> WorkflowId | None:
    """The enabled workflow the answer to a workflow question routes to when it is none of the offered ones."""
    prediction = ctx.services.router.route(ctx.text, ctx.language)
    owner = registry.owner(prediction.intent)
    if owner is None or owner not in ctx.enabled:
        return None
    ctx.prediction = prediction
    ctx.recorder.model(prediction.model)
    return owner


def follow_up_route(ctx: TurnContext, spec: StateSpec, route: Route) -> Route:
    """Continue the current workflow when the router is unsure of a message that follows up on the answer a
    context-holding state just gave ("¿y nomás en la de ahorro?" after balances, "e a de crédito?" after a card
    status, "y ahora el de abril" after a statement). Found in production QA (ACC-01, ACC-02, CRD-03): such turns got
    the generic workflow question or an off-topic abstention. A message the router places (another workflow's
    request, a person, an unsupported request) is never redirected, and the workflow's handlers and the kernel still
    decide everything that follows."""
    recognize = ctx.definition.follow_up
    if ctx.at_router or not spec.holds_context or route.kind not in UNSURE_ROUTES or recognize is None:
        return route
    intent = recognize(ctx)
    if intent is None or intent not in ctx.definition.intents:
        return route
    ctx.prediction = IntentPrediction(intent=intent, confidence=1.0, below_threshold=False, model=FOLLOW_UP_MODEL)
    ctx.recorder.model(FOLLOW_UP_MODEL)
    return Route(RouteKind.CONTINUE, target=ctx.workflow)


_STEPPED_UP = re.compile(
    r"\b(ya (me )?(confirme|verifique|valide|autentique)|ja (me )?(confirmei|verifiquei|validei|autentiquei)|"
    r"listo|pronto|hecho|feito|ya esta|ja esta|confirmad[oa]|confirmei|confirme)\b"
)
_WITHDRAWN = re.compile(r"\b(no|nao|cancel\w*|desist\w*|mejor no|melhor nao|olvidalo|esquece)\b")
"""Any refusal or cancellation marker: a continuation that also carries one is not a plain continuation."""


def continues_after_step_up(ctx: TurnContext) -> bool:
    """True when this turn says the step-up asked for in the same accepting state is done ("Listo, ya confirmé mi
    identidad", "Pronto, já confirmei minha identidade", a plain yes) and the session is now stepped up. Before QA
    finding CRE-14 such a turn was routed as a new message, got an off-topic answer, and the request was lost. The
    state's auth gate still evaluates the kernel again, so nothing is bypassed."""
    held = ctx.engine.step_up_state
    if held is None:
        return False
    ctx.engine = ctx.engine.evolve(step_up_state=None)
    if ctx.at_router or held != ctx.state or not ctx.snapshot.step_up_valid:
        return False
    return stepped_up_continuation(ctx.text)


def stepped_up_continuation(text: str) -> bool:
    """The plain "step-up done, go on" message (the web client's own, or a plain yes) with no refusal in it."""
    folded = fold(text)
    if _WITHDRAWN.search(folded):
        return False
    return bool(_STEPPED_UP.search(folded)) or (plain_answer(text) and parse_yes_no(text) is YesNo.YES)


def back_to_confirmation(ctx: TurnContext) -> None:
    """A turn that starts in a write's working state (the write paused there for a step-up) goes back to the
    write's confirmation state, so the incoming message is read as the answer to that confirmation. Found in
    production QA (R2): "no, mejor no la bloquees" sent after the step-up still blocked the card, because the
    working state ran the write without reading the message. Now a refusal cancels with the confirmation's own
    "nothing was recorded" reply, an unclear or unrelated message asks the confirmation again, and only a yes (or
    the plain step-up continuation handled before this) proceeds; the kernel still evaluates the write."""
    if ctx.at_router:
        return
    spec = ctx.definition.spec(ctx.state)
    if spec.kind is not StateKind.WORKING or not spec.action_policy_states or spec.resume_state is None:
        return
    if ctx.snapshot.step_up_valid and stepped_up_continuation(ctx.text):
        return
    try:
        ctx.definition.check_transition(ctx.state, spec.resume_state)
    except WorkflowTransitionError:
        return
    ctx.state = spec.resume_state


async def route_and_run(ctx: TurnContext, registry: WorkflowRegistry) -> Step:
    pending = await answer_pending(ctx, registry)
    if pending is not None:
        return pending
    if continues_after_step_up(ctx):
        return await run_handlers(ctx)
    back_to_confirmation(ctx)
    spec = ctx.definition.spec(ctx.state)
    current = None if ctx.at_router else ctx.workflow
    if ctx.at_router or spec.kind is StateKind.ACCEPTS_REQUEST:
        prediction = ctx.services.router.route(ctx.text, ctx.language)
        ctx.prediction = prediction
        ctx.recorder.model(prediction.model)
        route = dispatch(prediction, registry, current=current, mid_flow=spec.mid_flow)
        return await apply_route(ctx, registry, follow_up_route(ctx, spec, route))
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
