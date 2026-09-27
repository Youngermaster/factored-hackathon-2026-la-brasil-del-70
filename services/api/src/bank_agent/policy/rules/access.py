"""AUTH, PRV, and SCOPE rules: who may ask, what may be disclosed, and what the assistant may do at all."""

from bank_agent.domain.access import AuthLevel, Role
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.trust import RiskTier
from bank_agent.domain.workflow import CROSS_WORKFLOW_INTENTS, Intent
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_agent.policy.rules.context import CONVERSATION_RULES as RULES
from bank_agent.policy.rules.context import RuleContext
from bank_agent.policy.rules.registry import Verdict, fail, ok, str_list, typed_param


def required_level(context: RuleContext) -> AuthLevel:
    """The level this evaluation needs: the state's, the action's, and the elevated-risk level, whichever is higher.

    A higher risk tier can only raise the level, never lower it.
    """
    levels = [context.state_auth]
    if context.requirement is not None:
        levels.append(context.requirement.required_auth_level)
    base = max(levels, key=lambda level: level.rank)
    elevated = context.request.risk_tier.rank >= RiskTier.ELEVATED.rank
    if elevated and base.rank >= AuthLevel.OTP_VERIFIED.rank:
        bump = AuthLevel(typed_param(context.params, "elevated_risk_required_level", str))
        base = max(base, bump, key=lambda level: level.rank)
    return base


@RULES.rule(
    "AUTH.session_valid",
    version=1,
    reasons=("session_valid", "no_session_required", "session_missing", "session_expired", "not_a_customer_session"),
    missing_facts=("session",),
)
def session_valid(context: RuleContext) -> Verdict:
    session = context.request.session
    if session is None:
        if required_level(context) is AuthLevel.NONE:
            return ok("no_session_required")
        return fail(DecisionKind.DENY, "session_missing", missing=("session",))
    if session.expired:
        return fail(DecisionKind.DENY, "session_expired")
    if session.role is not Role.CUSTOMER:
        return fail(DecisionKind.DENY, "not_a_customer_session")
    return ok("session_valid")


@RULES.rule(
    "AUTH.required_level",
    version=1,
    params={"elevated_risk_required_level": str},
    reasons=("auth_level_sufficient", "step_up_required", "auth_level_insufficient"),
)
def auth_required_level(context: RuleContext) -> Verdict:
    required = required_level(context)
    session = context.request.session
    current = session.effective_auth_level if session is not None else AuthLevel.NONE
    if current.satisfies(required):
        return ok("auth_level_sufficient", required_level=required.value)
    if required is AuthLevel.STEP_UP and current.satisfies(AuthLevel.OTP_VERIFIED):
        return fail(DecisionKind.REQUIRE_STEP_UP, "step_up_required", required_level=required.value)
    return fail(DecisionKind.DENY, "auth_level_insufficient", required_level=required.value)


@RULES.rule(
    "AUTH.step_up_valid",
    version=1,
    params={"step_up_window_minutes": int},
    reasons=("step_up_not_required", "step_up_valid", "step_up_required", "step_up_needs_verified_session"),
)
def step_up_valid(context: RuleContext) -> Verdict:
    window = typed_param(context.params, "step_up_window_minutes", int)
    if context.requirement is None or not context.requirement.requires_step_up:
        return ok("step_up_not_required")
    session = context.request.session
    if session is not None and session.step_up_valid:
        return ok("step_up_valid", step_up_window_minutes=window)
    if session is None or not session.effective_auth_level.satisfies(AuthLevel.OTP_VERIFIED):
        return fail(DecisionKind.DENY, "step_up_needs_verified_session")
    return fail(DecisionKind.REQUIRE_STEP_UP, "step_up_required", step_up_window_minutes=window)


@RULES.rule("PRV.no_cross_customer_access", version=1, reasons=("no_cross_customer_access", "cross_customer_access"))
def no_cross_customer_access(context: RuleContext) -> Verdict:
    if context.facts.privacy.other_customer_reference:
        return fail(DecisionKind.REFUSE, "cross_customer_access")
    return ok("no_cross_customer_access")


@RULES.rule("PRV.no_third_party_disclosure", version=1, reasons=("no_third_party_request", "third_party_request"))
def no_third_party_disclosure(context: RuleContext) -> Verdict:
    if context.facts.privacy.third_party_request:
        return fail(DecisionKind.REFUSE, "third_party_request")
    return ok("no_third_party_request")


@RULES.rule(
    "SCOPE.workflow_supported",
    version=1,
    params={"supported_workflows": list},
    reasons=("workflow_supported", "workflow_not_supported"),
)
def workflow_supported(context: RuleContext) -> Verdict:
    workflow = context.request.workflow
    if workflow.value in str_list(context.params, "supported_workflows"):
        return ok("workflow_supported", workflow=workflow.value)
    return fail(DecisionKind.ABSTAIN, "workflow_not_supported", workflow=workflow.value)


@RULES.rule(
    "SCOPE.supported_intent",
    version=1,
    reasons=(
        "intent_supported",
        "intent_cross_workflow",
        "intent_unknown",
        "intent_unsupported",
        "intent_owned_by_other_workflow",
    ),
    missing_facts=("intent",),
)
def supported_intent(context: RuleContext) -> Verdict:
    intent = context.facts.intent
    if intent is None:
        return fail(DecisionKind.CLARIFY, "intent_unknown", missing=("intent",))
    if intent is Intent.UNSUPPORTED:
        return fail(DecisionKind.ABSTAIN, "intent_unsupported")
    if intent in CROSS_WORKFLOW_INTENTS:
        return ok("intent_cross_workflow", intent=intent.value)
    if WORKFLOW_CATALOG.workflow_for(intent) is context.request.workflow:
        return ok("intent_supported", intent=intent.value)
    return fail(DecisionKind.CLARIFY, "intent_owned_by_other_workflow", intent=intent.value)


@RULES.rule(
    "SCOPE.action_allowed_in_state",
    version=1,
    reasons=("no_action", "action_allowed", "action_not_allowed_in_workflow", "action_not_allowed_in_state"),
)
def action_allowed_in_state(context: RuleContext) -> Verdict:
    action = context.request.action
    if action is None:
        return ok("no_action")
    request = context.request
    if action.action not in WORKFLOW_CATALOG.descriptor(request.workflow).write_actions:
        return fail(DecisionKind.DENY, "action_not_allowed_in_workflow", action=action.action.value)
    if context.requirement is None or not context.requirement.allows(request.workflow, request.state):
        return fail(DecisionKind.DENY, "action_not_allowed_in_state", action=action.action.value)
    return ok("action_allowed", action=action.action.value)
