"""One evaluation run: scenarios, systems, runs, the language model mode, and the outputs.

Outputs in ``reports/eval/<run_id>/`` (gitignored, they hold transcripts): ``results.jsonl`` (one graded case per
line), ``metrics.json`` (``metrics.compute``), ``manifest.json`` (what ran: git sha, model label, prompt and policy
versions, scenario set hash, cassette mode and coverage, settings), and ``report.md``. Run 1 plays every selected
scenario; runs 2 and later play every scenario, or only the stratified variance subset (``repeat="subset"``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from bank_agent.bootstrap.settings import WorkflowSettings
from bank_agent.ports.llm import LLMClient
from bank_evals.meta import REPOSITORY_ROOT, generated_now, git_sha
from bank_evals.metrics.compute import system_metrics
from bank_evals.runner.cases import RESULTS, dump_json, run_cases
from bank_evals.runner.fake import FAKE_LABEL, smoke_llm
from bank_evals.runner.llm import LlmMode, RunLlm, build_run_llm
from bank_evals.runner.subset import smoke_subset, variance_subset
from bank_evals.runner.wiring import HarnessSettings, build_engine_parts, prompt_registry
from bank_evals.scenarios.model import Scenario, Split
from bank_evals.scenarios.store import check_lock, content_hash, load_split, split_path
from bank_evals.systems.base import SystemUnderTest
from bank_evals.systems.engine_system import EngineSystem
from bank_evals.systems.naive_agent.agent import NaiveAgentSystem
from bank_evals.users.simulated import SimulatedUser
from bank_evals.world import build_world
from bank_evals.world.model import WORLD_VERSION

DEFAULT_OUT = REPOSITORY_ROOT / "reports" / "eval"
SYSTEM_ORDER = ("b0", "p", "b1")


@dataclass
class RunOptions:
    run_id: str
    split: Split = Split.DEV
    systems: tuple[str, ...] = SYSTEM_ORDER
    runs: int = 1
    repeat: Literal["all", "subset"] = "subset"
    llm: LlmMode | Literal["fake"] = "off"
    driver: Literal["auto", "scripted"] = "auto"
    workflows: tuple[str, ...] = ()
    scenario_ids: tuple[str, ...] = ()
    limit: int | None = None
    out_dir: Path = DEFAULT_OUT
    cassette_dir: Path | None = None
    resume: bool = False
    workflow_overrides: dict[str, Any] = field(default_factory=dict)
    scenario_file: Path | None = None
    smoke: bool = False


@dataclass
class RunOutput:
    directory: Path
    manifest: dict[str, Any]
    metrics: dict[str, Any]
    results_count: int


def select(scenarios: list[Scenario], options: RunOptions) -> list[Scenario]:
    chosen = smoke_subset(scenarios) if options.smoke else scenarios
    chosen = [s for s in chosen if not options.workflows or (s.workflow and s.workflow.value in options.workflows)]
    if options.scenario_ids:
        chosen = [s for s in chosen if s.id in set(options.scenario_ids)]
    return chosen[: options.limit] if options.limit is not None else chosen


def plan_cases(scenarios: list[Scenario], systems: list[str], options: RunOptions) -> list[tuple[str, int, Scenario]]:
    repeated = variance_subset(scenarios) if options.repeat == "subset" else scenarios
    plan: list[tuple[str, int, Scenario]] = []
    for run_index in range(1, options.runs + 1):
        batch = scenarios if run_index == 1 else repeated
        for name in systems:
            plan.extend((name, run_index, scenario) for scenario in batch)
    return plan


def build_systems(options: RunOptions, settings: HarnessSettings, llm: RunLlm) -> tuple[dict[str, SystemUnderTest],
                                                                                          list[str]]:  # fmt: skip
    notes: list[str] = []
    systems: dict[str, SystemUnderTest] = {}
    parts = build_engine_parts(settings, llm) if {"p", "b0"} & set(options.systems) else None
    for name in options.systems:
        if name in {"p", "b0"} and parts is not None:
            systems[name] = EngineSystem(name, parts)
        elif name == "b1" and llm.available:
            systems[name] = NaiveAgentSystem(llm.client, llm.model_label)
        elif name == "b1":
            notes.append("B1 was not run: it needs a language model (--llm replay or record)")
    return systems, notes


async def execute(options: RunOptions, *, settings: HarnessSettings | None = None,
                  injected: LLMClient | None = None) -> RunOutput:  # fmt: skip
    """Run ``options`` end to end and write the outputs."""
    started = time.perf_counter()
    commit = git_sha()  # the code the run imported; a commit made while a long run plays is noted, not recorded
    base = settings or HarnessSettings()
    workflow = WorkflowSettings.model_validate({**base.workflow.model_dump(), **options.workflow_overrides})
    harness = HarnessSettings(workflow=workflow, policy=base.policy, retrieval=base.retrieval, llm=base.llm)
    source = options.scenario_file or split_path(options.split)
    locked = check_lock(source) if options.split is Split.TEST and options.scenario_file is None else None
    scenarios = select(load_split(source), options)
    directory = options.out_dir / options.run_id
    directory.mkdir(parents=True, exist_ok=True)
    cassettes = options.cassette_dir or (REPOSITORY_ROOT / "evals" / "cassettes" / "eval" / options.split.value)
    if options.llm == "fake":
        llm = build_run_llm(harness.llm, prompt_registry(), "inject", injected=smoke_llm(), label=FAKE_LABEL)
    else:
        llm = build_run_llm(harness.llm, prompt_registry(), options.llm, cassette_dir=cassettes, injected=injected)
    systems, notes = build_systems(options, harness, llm)
    simulator = SimulatedUser(llm.client) if llm.available and options.driver == "auto" else None
    plan = plan_cases(scenarios, [name for name in SYSTEM_ORDER if name in systems], options)
    world = build_world()
    results = await run_cases(systems, plan, world, run_id=options.run_id, out_dir=directory, simulator=simulator,
                              resume=options.resume)  # fmt: skip
    metrics = {name: system_metrics([r for r in results if r.system == name]) for name in systems}
    ended = git_sha()
    if ended != commit:
        notes.append(f"the checkout moved from {commit} to {ended} during the run; results come from {commit}")
    manifest = {
        "run_id": options.run_id, "generated_at": generated_now().isoformat(), "git_sha": commit,
        "split": options.split.value, "scenario_file": source.name, "scenario_set_hash": content_hash(source),
        "test_set_lock": locked, "scenarios": len(scenarios), "cases": len(results), "runs": options.runs,
        "repeat": options.repeat, "systems": {name: systems[name].model_label for name in systems},
        "llm_mode": options.llm, "model_label": llm.model_label, "driver": options.driver,
        "cassette_dir": str(cassettes.relative_to(REPOSITORY_ROOT)) if cassettes.is_relative_to(REPOSITORY_ROOT)
        else cassettes.name, "cassette_misses": dict(llm.misses.by_prompt),
        "workflow_settings": workflow.model_dump(
            mode="json", include={"router", "resolver", "risk_estimator", "llm_understanding", "llm_phrasing"}
        ),
        "prompts": sorted(str(ref) for ref in prompt_registry().refs), "world": WORLD_VERSION,
        "wall_clock_seconds": round(time.perf_counter() - started, 1), "notes": notes,
        "harness_errors": sum(1 for r in results if r.grade is None),
    }  # fmt: skip
    dump_json(directory / "manifest.json", manifest)
    dump_json(directory / "metrics.json", metrics)
    return RunOutput(directory, manifest, metrics, len(results))


RESULTS_FILE = RESULTS
