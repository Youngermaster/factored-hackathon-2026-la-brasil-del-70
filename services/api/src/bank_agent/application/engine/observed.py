"""The state handler call wrapped in a ``bank.workflow.state`` span (workflow id, state, and the next state)."""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.definition import StateSpec
from bank_agent.ports.telemetry import AttributeValue


async def run_state(ctx: TurnContext, spec: StateSpec) -> Step:
    attributes: dict[str, AttributeValue] = {
        "bank.workflow": ctx.workflow.value,
        "bank.state": ctx.state,
        "bank.state.kind": spec.kind.value,
    }
    with ctx.services.telemetry.span("bank.workflow.state", attributes) as span:
        step = await spec.handler(ctx)
        span.set_attribute("bank.state.next", step.next_state)
        span.set_attribute("bank.outcome", step.outcome.value)
        return step
