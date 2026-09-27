"""Assemble the execution record of a turn from the recorder and the context (no free-text reasoning field)."""

from datetime import datetime

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.domain.access import Channel
from bank_agent.domain.conversation import Conversation
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.workflow import Outcome, WorkflowRef

ROUTER_REF = WorkflowRef(id="router", version=1)


def build_record(
    ctx: TurnContext, before: Conversation, step: Step, channel: Channel, now: datetime
) -> ExecutionRecord:
    recorder = ctx.recorder
    outcome = step.outcome
    handoff_ref = ctx.handoff.handoff_id if ctx.handoff is not None else None
    if outcome is Outcome.ESCALATED and handoff_ref is None:
        handoff_ref = ctx.engine.handoff_id
    workflow = ROUTER_REF if ctx.at_router else ctx.definition.ref
    workflow_before = ctx.workflow_before if ctx.workflow_before != workflow else None
    return ExecutionRecord(
        turn_id=ctx.turn_id,
        conversation_id=before.conversation_id,
        customer_ref=ctx.customer.customer_id,
        session_ref=ctx.session.session_id,
        workflow=workflow,
        recorded_at=now,
        channel=channel,
        language=ctx.language,
        language_detection=ctx.detection,
        auth_level=ctx.snapshot.effective_auth_level,
        state_before=before.position.state,
        state_after=ctx.state,
        outcome=outcome,
        intent=ctx.prediction,
        decisions=tuple(recorder.decisions),
        clause_refs=recorder.clause_refs(),
        tool_calls=tuple(recorder.tool_calls),
        llm_calls=tuple(recorder.llm_calls),
        models=tuple(recorder.models.values()),
        prompts=tuple(recorder.prompts.values()),
        policy_pack_version=ctx.services.policy.pack.version,
        latency=recorder.latency(),
        token_usage=recorder.token_usage(),
        cost_usd=recorder.cost(),
        risk_tier=ctx.trust.risk_tier,
        trust_events_added=tuple(recorder.trust_events),
        grounding=recorder.grounding,
        safety_interventions=tuple(recorder.safety),
        handoff_ref=handoff_ref,
        case_refs=tuple(dict.fromkeys(recorder.case_refs)),
        workflow_before=workflow_before,
        retrieval=recorder.retrieval,
        risk_estimates=tuple(recorder.risk_estimates),
        eligibility_assessments=tuple(recorder.eligibility_assessments),
    )
