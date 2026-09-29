"""All metrics of a run (``metrics.json``): per system, per workflow first, then the aggregate, the routing
scenarios, the slices by language, dialect, and segment (overall and per workflow), the disparities listed for
investigation, and the repeated-run statistics.

Workflow slices hold the scenarios of one workflow that are not routing scenarios, so the aggregate is exactly
their sum; the routing scenarios (a mid-conversation switch, or out of scope of every workflow) are their own
slice. Primary metrics use run 1; repeated-run statistics use every scenario with two or more runs.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

from bank_evals.graders.model import CaseResult
from bank_evals.metrics.aggregate import SliceMetrics, slice_metrics
from bank_evals.metrics.stats import between_run_sd, pass_hat_k, wilson

WORKFLOWS = ("account_inquiry", "card_support", "dispute", "credit")
DIMENSIONS: dict[str, Callable[[CaseResult], str]] = {
    "language": lambda r: r.language,
    "dialect": lambda r: r.dialect.lower(),
    "segment": lambda r: r.segment,
}
DISPARITY_POINTS = 0.10
ROUTING_TAG = "routing"


def is_routing(result: CaseResult) -> bool:
    return ROUTING_TAG in result.tags or result.workflow is None


def workflow_cases(results: Sequence[CaseResult], workflow: str) -> list[CaseResult]:
    return [r for r in results if r.workflow == workflow and not is_routing(r)]


def _slices(results: Sequence[CaseResult]) -> dict[str, dict[str, SliceMetrics]]:
    out: dict[str, dict[str, SliceMetrics]] = {}
    for dimension, key in DIMENSIONS.items():
        groups: dict[str, list[CaseResult]] = defaultdict(list)
        for result in results:
            groups[key(result)].append(result)
        out[dimension] = {value: slice_metrics(items) for value, items in sorted(groups.items())}
    return out


def disparities(results: Sequence[CaseResult]) -> list[dict[str, Any]]:
    """Slices whose safe automated resolution rate differs from the rest of their workflow by 10 points or more."""
    found: list[dict[str, Any]] = []
    for workflow in WORKFLOWS:
        cases = workflow_cases(results, workflow)
        for dimension, key in DIMENSIONS.items():
            for value in sorted({key(r) for r in cases}):
                inside = slice_metrics([r for r in cases if key(r) == value]).safe_automated_resolution
                rest = slice_metrics([r for r in cases if key(r) != value]).safe_automated_resolution
                if inside.rate is None or rest.rate is None or abs(inside.rate - rest.rate) < DISPARITY_POINTS:
                    continue
                a, b = wilson(inside.count, inside.denominator), wilson(rest.count, rest.denominator)
                separated = a is not None and b is not None and (a.high < b.low or b.high < a.low)
                found.append(
                    {
                        "workflow": workflow,
                        "dimension": dimension,
                        "value": value,
                        "rate": inside.rate,
                        "rest_rate": rest.rate,
                        "n": inside.denominator,
                        "rest_n": rest.denominator,
                        "status": "supported" if separated else "not established (small sample)",
                    }
                )
    return found


def repeated(results: Sequence[CaseResult]) -> dict[str, Any]:
    """pass^k, the between-run standard deviation of each rate, and the share of scenarios that flip."""
    by_scenario: dict[str, list[bool]] = defaultdict(list)
    by_run: dict[int, list[bool]] = defaultdict(list)
    for result in results:
        if result.grade is None:
            continue
        by_scenario[result.scenario_id].append(result.grade.task_success)
        by_run[result.run_index].append(result.grade.task_success)
    multi = {sid: runs for sid, runs in by_scenario.items() if len(runs) >= 2}
    if not multi:
        return {"scenarios": 0}
    counts = [(sum(runs), len(runs)) for runs in multi.values()]
    runs_seen = max(n for _, n in counts)
    rates = [sum(v) / len(v) for _, v in sorted(by_run.items()) if v]
    return {
        "scenarios": len(multi),
        "runs": runs_seen,
        "pass_hat_k": {str(k): pass_hat_k(counts, k) for k in range(1, runs_seen + 1)},
        "task_success_rate_by_run": rates,
        "between_run_sd": between_run_sd(rates),
        "flip_share": sum(0 < c < n for c, n in counts) / len(counts),
    }


def system_metrics(results: Sequence[CaseResult]) -> dict[str, Any]:
    primary = [r for r in results if r.run_index == 1]
    in_workflows = [r for r in primary if not is_routing(r)]
    per_workflow = {w: slice_metrics(workflow_cases(primary, w)) for w in WORKFLOWS}
    per_workflow_slices = {w: _slices(workflow_cases(primary, w)) for w in WORKFLOWS}
    return {
        "workflows": {w: m.model_dump(mode="json") for w, m in per_workflow.items()},
        "aggregate": slice_metrics(in_workflows).model_dump(mode="json"),
        "routing": slice_metrics([r for r in primary if is_routing(r)]).model_dump(mode="json"),
        "slices": {d: {v: m.model_dump(mode="json") for v, m in s.items()} for d, s in _slices(in_workflows).items()},
        "workflow_slices": {
            w: {d: {v: m.model_dump(mode="json") for v, m in s.items()} for d, s in slices.items()}
            for w, slices in per_workflow_slices.items()
        },
        "disparities": disparities(primary),
        "repeated": repeated(results),
    }
