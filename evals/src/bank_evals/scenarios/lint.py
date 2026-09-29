"""The generator lint (not part of the contract): the mix, the languages, and the workflow labels.

It fails when an in-scope scenario has no ``workflow``, when a workflow slice misses a category or a language of
the plan, when a cell's count differs from the plan, when a routing path names an unregistered workflow, or when a
simulated scenario has no scripted fallback.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from bank_agent.domain.workflow import WorkflowId
from bank_evals.scenarios.mix import PER_WORKFLOW, ROUTING, ROUTING_TAG, WORKFLOWS
from bank_evals.scenarios.model import Scenario, ScenarioCategory, ScenarioMode, Split

C = ScenarioCategory
LANGUAGE_PATHS = (
    ("normal", {C.NORMAL}),
    ("ambiguous or unsupported", {C.AMBIGUOUS, C.UNSUPPORTED}),
    ("human_required", {C.HUMAN_REQUIRED}),
)


def lint(scenarios: Sequence[Scenario], split: Split) -> list[str]:
    problems: list[str] = []
    registered = {item.value for item in WorkflowId}
    for scenario in scenarios:
        if scenario.in_scope and scenario.workflow is None:
            problems.append(f"{scenario.id}: in scope without a workflow")
        for workflow in scenario.expected_workflow_path:
            if workflow.value not in registered:
                problems.append(f"{scenario.id}: unregistered workflow {workflow.value} in the path")
        if scenario.mode is ScenarioMode.SIMULATED and not scenario.scripted_fallback:
            problems.append(f"{scenario.id}: simulated without scripted fallback turns")
    routing = [s for s in scenarios if ROUTING_TAG in s.tags]
    core = [s for s in scenarios if ROUTING_TAG not in s.tags]
    for workflow in WORKFLOWS:
        mine = [s for s in core if s.workflow is workflow]
        counts = Counter(s.category for s in mine)
        for category, expected in PER_WORKFLOW[split].items():
            if counts[category] != expected:
                problems.append(f"{workflow.value}: {counts[category]} {category.value}, the plan has {expected}")
        for label, categories in LANGUAGE_PATHS:
            languages = {s.language.value for s in mine if s.category in categories}
            if languages != {"es", "pt"}:
                problems.append(f"{workflow.value}: the {label} path lacks a language ({sorted(languages)})")
    out_of_scope = [s for s in routing if s.workflow is None]
    switches = [s for s in routing if s.expected_workflow_path]
    if len(out_of_scope) != ROUTING[split]["out_of_scope"]:
        problems.append(
            f"routing: {len(out_of_scope)} out-of-scope scenarios, the plan has {ROUTING[split]['out_of_scope']}"
        )
    if len(switches) != ROUTING[split]["switch"]:
        problems.append(f"routing: {len(switches)} switch scenarios, the plan has {ROUTING[split]['switch']}")
    return problems
