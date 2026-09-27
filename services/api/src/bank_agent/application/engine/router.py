"""Router dispatch: map an ``IntentRouter`` prediction through the catalog and the enabled set to a route.

The rules (a pure function, tested as a table):

- An uncertain prediction offers the two most likely enabled workflows (from the candidates, then catalog order).
- ``informational``, ``human_request``, and ``greeting_or_other`` are shared handlers in any workflow;
  ``unsupported``, an intent no workflow owns, and an intent of a workflow that is not enabled are out of scope.
- An intent of the current workflow continues it. Before any workflow, the owner starts. Mid-flow (a pending
  answer, confirmation, or execution) a request for another workflow is confirmed first; otherwise it switches.
"""

from dataclasses import dataclass
from enum import StrEnum

from bank_agent.application.engine.registry import WorkflowRegistry
from bank_agent.domain.intelligence import IntentPrediction
from bank_agent.domain.workflow import Intent, WorkflowId

GREETING_MATCHED = 0.5


class RouteKind(StrEnum):
    CONTINUE = "continue"
    START = "start"
    SWITCH = "switch"
    CONFIRM_SWITCH = "confirm_switch"
    OUT_OF_SCOPE = "out_of_scope"
    INFORMATIONAL = "informational"
    HUMAN = "human"
    GREETING = "greeting"
    CLARIFY_WORKFLOW = "clarify_workflow"


@dataclass(frozen=True)
class Route:
    kind: RouteKind
    target: WorkflowId | None = None
    options: tuple[WorkflowId, ...] = ()


_SHARED = {
    Intent.INFORMATIONAL: RouteKind.INFORMATIONAL,
    Intent.HUMAN_REQUEST: RouteKind.HUMAN,
    Intent.GREETING_OR_OTHER: RouteKind.GREETING,
    Intent.UNSUPPORTED: RouteKind.OUT_OF_SCOPE,
}


def likely_workflows(prediction: IntentPrediction, registry: WorkflowRegistry) -> tuple[WorkflowId, ...]:
    ranked = [registry.owner(candidate.intent) for candidate in prediction.candidates]
    ordered = [workflow for workflow in ranked if workflow is not None]
    ordered.extend(registry.ordered_enabled())
    return tuple(dict.fromkeys(ordered))[:2]


def dispatch(
    prediction: IntentPrediction, registry: WorkflowRegistry, *, current: WorkflowId | None, mid_flow: bool
) -> Route:
    intent = prediction.intent
    greeting = intent is Intent.GREETING_OR_OTHER and prediction.confidence >= GREETING_MATCHED
    if prediction.below_threshold and not greeting:
        options = likely_workflows(prediction, registry)
        if len(options) == 2:
            return Route(RouteKind.CLARIFY_WORKFLOW, options=options)
        if len(options) == 1:
            return Route(RouteKind.CONTINUE if options[0] is current else RouteKind.START, target=options[0])
        return Route(RouteKind.GREETING)
    if intent in _SHARED:
        return Route(_SHARED[intent])
    owner = registry.owner(intent)
    if owner is None:
        return Route(RouteKind.OUT_OF_SCOPE)
    if owner is current:
        return Route(RouteKind.CONTINUE, target=owner)
    if current is None:
        return Route(RouteKind.START, target=owner)
    return Route(RouteKind.CONFIRM_SWITCH if mid_flow else RouteKind.SWITCH, target=owner)
