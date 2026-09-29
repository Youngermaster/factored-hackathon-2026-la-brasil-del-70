"""The run report (``report.md``), the published results (``docs/evaluation/results.md``), and the failure
table (``docs/evaluation/failures.md``). Every document states how its numbers were obtained."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from bank_evals.graders.model import CaseResult
from bank_evals.metrics.compute import WORKFLOWS, is_routing
from bank_evals.reports.tables import metrics_table, rate, unsafe_rate, unsafe_types_table
from bank_evals.systems.historical import LABEL as HISTORICAL_LABEL
from bank_evals.systems.historical import historical_table, load_historical

SYSTEM_NAMES = {"b0": "B0 (menu and rules bot)", "b1": "B1 (naive LLM agent)", "p": "P (proposed system)"}
MEASUREMENT = (
    "**Measurement label: simulated, offline.** Scripted and model-played customers on a synthetic evaluation "
    "world; not a production measurement. Projected figures are labeled projected."
)


def header(manifest: dict[str, Any], title: str) -> list[str]:
    systems = ", ".join(f"{SYSTEM_NAMES.get(k, k)}: `{v}`" for k, v in manifest["systems"].items())
    misses = sum(manifest.get("cassette_misses", {}).values())
    return [
        f"# {title}", "",
        f"Generated {manifest['generated_at']} from commit `{manifest['git_sha']}`; run `{manifest['run_id']}` on the "
        f"{manifest['split']} split (`{manifest['scenario_file']}`, SHA-256 `{manifest['scenario_set_hash'][:16]}`), "
        f"{manifest['scenarios']} scenarios, {manifest['runs']} run(s), language model mode `{manifest['llm_mode']}`, "
        f"cassette misses {misses}, harness errors {manifest.get('harness_errors', 0)}.", "",
        f"Systems and model labels: {systems}.", "", MEASUREMENT, "",
    ]  # fmt: skip


def _columns(metrics: dict[str, Any], section: str, key: str | None = None) -> list[tuple[str, dict[str, Any]]]:
    columns = []
    for system in ("b0", "b1", "p"):
        if system in metrics:
            block = metrics[system][section] if key is None else metrics[system][section][key]
            columns.append((SYSTEM_NAMES[system], block))
    return columns


def workflow_sections(metrics: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for workflow in WORKFLOWS:
        columns = _columns(metrics, "workflows", workflow)
        lines += [f"## `{workflow}`", "", *metrics_table(columns), "", *unsafe_types_table(columns), ""]
    columns = _columns(metrics, "aggregate")
    lines += ["## Aggregate (the four workflows, never read alone)", "", *metrics_table(columns), "",
              *unsafe_types_table(columns), ""]  # fmt: skip
    columns = _columns(metrics, "routing")
    lines += ["## Routing scenarios (switches and requests out of every workflow)", "", *metrics_table(columns), ""]
    return lines


def slice_sections(metrics: dict[str, Any]) -> list[str]:
    lines = ["## Slices (safe automated resolution and unsafe outcomes)", ""]
    for dimension in ("language", "dialect", "segment"):
        lines += [f"### By {dimension}", "", "| System | Value | Cases | Safe automated resolution | Unsafe outcomes |",
                  "|---|---|---|---|---|"]  # fmt: skip
        for system, data in metrics.items():
            for value, block in data["slices"][dimension].items():
                small = " (small)" if block["small_cell"] else ""
                sar, unsafe = rate(block["safe_automated_resolution"]), unsafe_rate(block["unsafe_outcomes"])
                lines.append(f"| {system.upper()} | {value} | {block['cases']}{small} | {sar} | {unsafe} |")
        lines.append("")
    lines += ["### Disparities listed for investigation (10 points or more from the rest of the workflow)", ""]
    found = [(s, d) for s, data in metrics.items() for d in data["disparities"]]
    lines += ["| System | Workflow | Dimension | Value | Rate | Rest | Status |", "|---|---|---|---|---|---|---|"]
    for s, d in found:
        inside, rest = f"{100 * d['rate']:.0f}% (n={d['n']})", f"{100 * d['rest_rate']:.0f}% (n={d['rest_n']})"
        lines.append(
            f"| {s.upper()} | `{d['workflow']}` | {d['dimension']} | {d['value']} | {inside} | {rest} | {d['status']} |"
        )
    if not found:
        lines.append("| none | | | | | | |")
    return [*lines, ""]


def repeated_section(metrics: dict[str, Any]) -> list[str]:
    lines = [
        "## Repeated runs",
        "",
        "| System | Scenarios | Runs | pass^1 | pass^k (k = runs) | Between-run SD | Flip share |",
        "|---|---|---|---|---|---|---|",
    ]
    for system, data in metrics.items():
        rep = data["repeated"]
        if not rep.get("scenarios"):
            lines.append(f"| {system.upper()} | 0 | 1 | n/a | n/a | n/a | n/a |")
            continue
        passes, runs = rep["pass_hat_k"], rep["runs"]
        sd = "n/a" if rep["between_run_sd"] is None else f"{100 * rep['between_run_sd']:.1f} points"
        lines.append(f"| {system.upper()} | {rep['scenarios']} | {runs} | {100 * passes['1']:.0f}% | "
                     f"{100 * passes[str(runs)]:.0f}% | {sd} | {100 * rep['flip_share']:.0f}% |")  # fmt: skip
    return [*lines, ""]


def historical_section() -> list[str]:
    references = load_historical()
    if not references:
        return []
    return ["## H: historical reference (not scored on scenarios)", "", f"Label: {HISTORICAL_LABEL}.", "",
            *historical_table(references), ""]  # fmt: skip


def review_section(results: Sequence[CaseResult]) -> list[str]:
    lines = ["## Scenario review status", "", "| Workflow | Scenarios | Reviewed |", "|---|---|---|"]
    first = {r.scenario_id: r for r in results}.values()
    for workflow in (*WORKFLOWS, None):
        mine = [r for r in first if r.workflow == workflow]
        reviewed = sum(r.review_status == "approved" for r in mine)
        state = "pending human review" if not reviewed else "partial"
        lines.append(f"| {workflow or 'routing, out of scope'} | {len(mine)} | {reviewed} ({state}) |")
    return [*lines, ""]


def render_report(manifest: dict[str, Any], metrics: dict[str, Any], results: Sequence[CaseResult],
                  title: str = "Evaluation run report") -> str:  # fmt: skip
    lines = [*header(manifest, title), *workflow_sections(metrics), *slice_sections(metrics),
             *repeated_section(metrics), *historical_section(), *review_section(results)]  # fmt: skip
    notes = manifest.get("notes") or []
    if notes:
        lines += ["## Notes", "", *[f"- {note}" for note in notes], ""]
    return "\n".join(lines).rstrip() + "\n"


def render_failures(manifest: dict[str, Any], results: Sequence[CaseResult], status: dict[str, str] | None = None,
                    title: str = "Evaluation failures") -> str:  # fmt: skip
    status = status or {}
    lines = [*header(manifest, title), "One row per failed case (task failure, unsafe outcome, or policy finding).", ""]
    groups: dict[str, list[CaseResult]] = {w: [] for w in (*WORKFLOWS, "routing")}
    for result in results:
        if result.grade is None or (result.grade.task_success and not result.grade.unsafe
                                    and result.grade.policy_compliant):  # fmt: skip
            continue
        groups["routing" if is_routing(result) else str(result.workflow)].append(result)
    for name, items in groups.items():
        lines += [
            f"## `{name}`",
            "",
            "| Scenario | Category | System | Expected | Observed | Root cause | Findings | Fix status |",
            "|---|---|---|---|---|---|---|---|",
        ]
        causes = Counter(r.grade.root_cause for r in items if r.grade)
        for r in sorted(items, key=lambda r: (r.scenario_id, r.system, r.run_index)):
            grade = r.grade
            if grade is None:
                continue
            findings = "; ".join(sorted({f.code for f in grade.findings}))[:160]
            fix = status.get(f"{r.scenario_id}:{r.system}", "open")
            lines.append(f"| `{r.scenario_id}` | {r.category} | {r.system.upper()} | {r.expected_outcome} | "
                         f"{grade.final_outcome} | {grade.root_cause or 'none'} | {findings} | {fix} |")  # fmt: skip
        if not items:
            lines.append("| none | | | | | | | |")
        lines += ["", "Root causes: " + (", ".join(f"{k} {v}" for k, v in causes.most_common()) or "none") + ".", ""]
    return "\n".join(lines).rstrip() + "\n"
