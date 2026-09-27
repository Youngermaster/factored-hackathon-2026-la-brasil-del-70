"""Handlers every workflow shares: AUTH_REQUIRED (re-authentication and resume), the accepting end states, and
ESCALATED. Workflows register them in their definitions like any other handler."""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.definition import AUTH_REQUIRED, ESCALATED, StateKind, StateSpec
from bank_agent.application.engine.reply import Reply
from bank_agent.domain.access import AuthLevel
from bank_agent.domain.conversation import NoticeCode
from bank_agent.domain.errors import StepUpRequiredError
from bank_agent.domain.workflow import Outcome

UNDERSTAND = "UNDERSTAND"
REAUTH_NOTICES = (NoticeCode.SESSION_EXPIRED, NoticeCode.REAUTHENTICATION_REQUIRED)


def auth_required_reply() -> Reply:
    return Reply(template="common.auth_required", notices=REAUTH_NOTICES)


async def auth_required(ctx: TurnContext) -> Step:
    """Resume at the last safe state once the session is verified again; otherwise keep asking."""
    if not ctx.snapshot.effective_auth_level.satisfies(AuthLevel.OTP_VERIFIED):
        return Step(AUTH_REQUIRED, auth_required_reply())
    target = ctx.engine.resume_state or ctx.definition.entry_state
    ctx.engine = ctx.engine.evolve(resume_state=None)
    ctx.resumed = True
    ctx.reprompt = True
    return Step(target)


async def accept_request(ctx: TurnContext) -> Step:
    """RESOLVED, ABSTAINED, and REFUSED: a new request for this workflow starts over at UNDERSTAND."""
    return Step(UNDERSTAND)


async def escalated(ctx: TurnContext) -> Step:
    """The conversation is with a person already; say so again, with the same handoff."""
    reply = Reply(template="common.escalated_already", params={"due": ctx.engine.handoff_due or ctx.today})
    return Step(ESCALATED, reply, Outcome.ESCALATED)


def auth_required_state(policy_state: str = "START") -> StateSpec:
    return StateSpec(name=AUTH_REQUIRED, policy_state=policy_state, handler=auth_required, kind=StateKind.WORKING)


def end_state(name: str, policy_state: str = "START") -> StateSpec:
    return StateSpec(name=name, policy_state=policy_state, handler=accept_request, kind=StateKind.ACCEPTS_REQUEST)


def escalated_state(policy_state: str = "ESCALATE") -> StateSpec:
    return StateSpec(name=ESCALATED, policy_state=policy_state, handler=escalated, kind=StateKind.TERMINAL)


def require_step_up(ctx: TurnContext) -> None:
    """Raise when the session has no valid step-up window (the engine answers with a step-up request)."""
    if not ctx.snapshot.step_up_valid:
        raise StepUpRequiredError()
