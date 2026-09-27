"""The workflow registry: one validated ``WorkflowDefinition`` per ``WorkflowId`` and the enabled set.

``build_registry`` checks everything a turn will rely on and raises ``WorkflowRegistryError`` (a configuration
error, so a startup error) listing every problem: an enabled workflow without a definition, a definition outside the
catalog or with other intents than the catalog's, a policy state that is not canonical or not bound for every
country and language, an engine-only tool on an allowlist, and a write tool in a state that the policy matrix does
not allow for that action or that the workflow may not perform. Adding a workflow means a definition, its
bindings, and its tests; the engine does not change. Intents of a workflow that is not enabled go to the
out-of-scope handler, which is also how the cut rule of CLAUDE.md section 1 is applied.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from bank_agent.application.engine.definition import WorkflowDefinition
from bank_agent.domain.actions import WRITE_TOOLS, ActionKind, ToolName
from bank_agent.domain.errors import WorkflowRegistryError
from bank_agent.domain.policy import ActionRequirement
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.domain.workflow_catalog import WorkflowCatalog

ENGINE_ONLY_TOOLS = frozenset({ToolName.GET_MY_CREDIT_PROFILE})


class BindingCoverage(Protocol):
    """``BoundPolicyLookup`` satisfies it: whether a state is bound for every country and language."""

    def covers(self, workflow: WorkflowId, state: str) -> bool: ...


class ActionMatrix(Protocol):
    """``PolicyPack`` satisfies it: the policy matrix row of a write action."""

    def action_requirements(self, action: ActionKind) -> ActionRequirement: ...


MAX_REPORTED = 12


@dataclass(frozen=True)
class WorkflowRegistry:
    name: str
    definitions: Mapping[WorkflowId, WorkflowDefinition]
    enabled: frozenset[WorkflowId]
    catalog: WorkflowCatalog

    def definition(self, workflow: WorkflowId) -> WorkflowDefinition:
        return self.definitions[workflow]

    def owner(self, intent: Intent) -> WorkflowId | None:
        """The enabled workflow that owns ``intent``, or ``None`` (cross-workflow, unowned, or not enabled)."""
        owner = self.catalog.workflow_for(intent)
        return owner if owner is not None and owner in self.enabled else None

    def ordered_enabled(self) -> tuple[WorkflowId, ...]:
        return tuple(workflow for workflow in self.catalog.ids() if workflow in self.enabled)


def _check_definition(
    definition: WorkflowDefinition, catalog: WorkflowCatalog, bound: BindingCoverage, pack: ActionMatrix
) -> list[str]:
    problems: list[str] = []
    workflow = definition.workflow
    descriptor = catalog.descriptor(workflow)
    if definition.intents != frozenset(descriptor.intents):
        problems.append(f"{workflow}: the definition's intents differ from the catalog's")
    for spec in definition.states.values():
        where = f"{workflow}.{spec.name}"
        policy_states = {spec.policy_state, *spec.action_policy_states.values()}
        for state in sorted(policy_states):
            if state not in descriptor.states:
                problems.append(f"{where}: {state} is not a canonical state of {workflow}")
            elif not bound.covers(workflow, state):
                problems.append(f"{where}: {state} is not bound for every country and language")
        for action, state in spec.action_policy_states.items():
            if action not in descriptor.write_actions:
                problems.append(f"{where}: {workflow} may not perform {action}")
            elif not pack.action_requirements(action).allows(workflow, state):
                problems.append(f"{where}: the policy matrix does not allow {action} in {state}")
        for tool in sorted(spec.allowed_tools):
            if tool in ENGINE_ONLY_TOOLS:
                problems.append(f"{where}: {tool} is engine only and cannot be on an allowlist")
            elif tool in WRITE_TOOLS and ActionKind(tool.value) not in spec.action_policy_states:
                problems.append(f"{where}: write tool {tool} needs a policy state for its action")
    return problems


def build_registry(
    name: str,
    definitions: Mapping[WorkflowId, WorkflowDefinition],
    *,
    catalog: WorkflowCatalog,
    bound: BindingCoverage,
    pack: ActionMatrix,
    enabled: frozenset[WorkflowId],
) -> WorkflowRegistry:
    problems: list[str] = []
    known = set(catalog.ids())
    for workflow in sorted(enabled - set(definitions)):
        problems.append(f"{workflow} is enabled but has no definition")
    for workflow, definition in sorted(definitions.items()):
        if definition.workflow is not workflow:
            problems.append(f"{workflow} is registered with the definition of {definition.workflow}")
        elif workflow not in known:
            problems.append(f"{workflow} is not in the workflow catalog")
        else:
            problems.extend(_check_definition(definition, catalog, bound, pack))
    if problems:
        shown = "; ".join(problems[:MAX_REPORTED])
        more = len(problems) - MAX_REPORTED
        raise WorkflowRegistryError(f"registry {name}: {shown}" + (f"; and {more} more" if more > 0 else ""))
    return WorkflowRegistry(name=name, definitions=dict(definitions), enabled=enabled, catalog=catalog)
