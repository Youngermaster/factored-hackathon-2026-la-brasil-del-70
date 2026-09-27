"""EXECUTE and VERIFY for any workflow: confirmed writes, idempotent by key, reported only after a read-back.

``execute_writes`` evaluates each confirmed ``ActionRequest`` in its binding state (the kernel checks the matrix,
step-up, and every rule again), skips a write this conversation already executed and verified, and calls the
tool through the guarded toolset (bounded retries for transient failures only). A failure after retries escalates
with the facts verified so far. ``verify_writes`` reads every new write back; a mismatch or an unknown result
escalates with ``verification_mismatch``, and only a positive read-back becomes a verified action a reply may claim.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.data import ExecutedAction
from bank_agent.application.engine.decide import evaluate, explanation
from bank_agent.application.engine.shared import abstain, blocking_step, escalate, escalate_decision
from bank_agent.application.grounding.draft import VerifiedAction
from bank_agent.domain.actions import ActionRequest, ActionResult, ActionStatus, ToolName, Verification
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.errors import AuthenticationError, AuthorizationError, DomainError, ToolError
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.execution_record import ToolCallStatus
from bank_agent.domain.identifiers import CaseId, SourceRef
from bank_agent.policy.facts import CardFacts, CreditFacts, DisputeFacts


@dataclass(frozen=True)
class PlannedWrite:
    request: ActionRequest
    policy_state: str
    run: Callable[[], Awaitable[SourceRef]]
    dispute: DisputeFacts | None = None
    card: CardFacts | None = None
    credit: CreditFacts | None = None
    denied_template: str = "dispute.denied"
    """What the customer hears when the kernel no longer allows the confirmed write."""


@dataclass(frozen=True)
class ReadBack:
    tool: ToolName
    idempotency_key: str
    check: Callable[[], Awaitable[Verification]]


def _attempts(ctx: TurnContext, tool: ToolName) -> int:
    calls = [c for c in ctx.recorder.tool_calls if c.tool is tool and c.status is ToolCallStatus.OK]
    return calls[-1].attempts if calls else 1


async def execute_writes(ctx: TurnContext, writes: list[PlannedWrite], *, state: str) -> Step | None:
    for write in writes:
        request = write.request
        done = ctx.engine.executed_for(request.idempotency_key)
        if done is not None and done.verified:
            continue
        decision = evaluate(
            ctx,
            policy_state=write.policy_state,
            action=request,
            dispute=write.dispute,
            card=write.card,
            credit=write.credit,
        )
        stop = blocking_step(ctx, decision, state=state)
        if stop is not None:
            return stop
        if decision.kind is not DecisionKind.ALLOW:
            return abstain(ctx, write.denied_template, explanation(decision))
        failed = ExecutedAction(
            action=request.action, target=request.target, idempotency_key=request.idempotency_key, failed=True
        )
        try:
            outcome = await write.run()
        except ToolError as error:
            ctx.engine = ctx.engine.with_executed(failed)
            decision = evaluate(ctx, policy_state=write.policy_state, tool_failures=1)
            if decision.kind is DecisionKind.ESCALATE:
                return escalate_decision(ctx, decision)
            return escalate(ctx, EscalationReasonCode.TOOL_FAILURE, error.code, decision=decision)
        except (AuthenticationError, AuthorizationError):
            raise
        except DomainError as error:
            ctx.engine = ctx.engine.with_executed(failed)
            return escalate(ctx, EscalationReasonCode.TOOL_FAILURE, error.code)
        ctx.engine = ctx.engine.with_executed(
            ExecutedAction(
                action=request.action,
                target=request.target,
                idempotency_key=request.idempotency_key,
                outcome_ref=outcome,
            )
        )
    return None


async def verify_writes(ctx: TurnContext, reads: list[ReadBack], *, case_ref: CaseId | None = None) -> Step | None:
    for read in reads:
        done = ctx.engine.executed_for(read.idempotency_key)
        if done is None or done.failed:
            continue
        verification = await read.check()
        ctx.tools.attach_verification(read.tool, verification)
        result = ActionResult(
            action=done.action,
            idempotency_key=done.idempotency_key,
            status=ActionStatus.EXECUTED,
            outcome_ref=done.outcome_ref,
            attempts=_attempts(ctx, read.tool),
            completed_at=ctx.now,
        )
        ctx.recorder.verified_actions.append(VerifiedAction(result=result, verification=verification))
        if not verification.verified:
            ctx.engine = ctx.engine.with_executed(done.evolve(verified=False, mismatch_code=verification.mismatch_code))
            decision = evaluate(ctx, verification_mismatch=True)
            return escalate_decision(ctx, decision, case_ref=case_ref)
        ctx.engine = ctx.engine.with_executed(done.evolve(verified=True, mismatch_code=None))
        if done.outcome_ref is not None:
            ctx.engine = ctx.engine.with_fact(f"{done.action.value} verified by read-back", done.outcome_ref)
    return None
