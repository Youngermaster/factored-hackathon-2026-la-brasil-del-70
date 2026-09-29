"""Play and grade cases: one scenario, one system, one run index, into one ``CaseResult``.

Results are appended to ``results.jsonl`` as each case finishes, so a long local run can be inspected while it
runs and resumed (``--resume`` skips the cases already written). A case that raises is a harness error: it is
written with the error and excluded from every metric, and the reports count it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path

from bank_evals.graders.grade import grade
from bank_evals.graders.model import CaseResult
from bank_evals.scenarios.model import Scenario, ScenarioMode
from bank_evals.systems.base import LlmCallView, SystemUnderTest, Transcript
from bank_evals.users.scripted import play_scripted
from bank_evals.users.simulated import SimulatedUser
from bank_evals.world.model import World

LOGGER = logging.getLogger(__name__)
RESULTS = "results.jsonl"


def segment_of(scenario: Scenario, world: World) -> str:
    return world.persona(scenario.persona_ref).customer.segment.value


async def play_case(
    system: SystemUnderTest,
    scenario: Scenario,
    world: World,
    *,
    run_id: str,
    run_index: int,
    simulator: SimulatedUser | None,
) -> CaseResult:
    transcript = Transcript(
        scenario_id=scenario.id, system=system.name, run_index=run_index, model_label=system.model_label
    )
    user_calls: list[LlmCallView] = []
    driver = "scripted"
    try:
        case = await system.start(scenario, world, run_index=run_index)
        if scenario.mode is ScenarioMode.SIMULATED:
            if simulator is not None:
                before = len(simulator.calls)
                turns = await simulator.play(case, scenario, run_index)
                user_calls = simulator.calls[before:]
                transcript.user_calls = list(user_calls)
            else:
                turns = await play_scripted(case, scenario, scenario.scripted_fallback, driver="scripted_fallback")
        else:
            turns = await play_scripted(case, scenario, scenario.turns)
        transcript.turns = turns
        transcript.end_state = await case.finish()
        driver = turns[0].driver if turns else driver
    except Exception as error:
        LOGGER.warning("case %s on %s failed: %s", scenario.id, system.name, type(error).__name__)
        transcript.error = f"{type(error).__name__}: {error}"[:500]
    graded = None if transcript.error else grade(scenario, transcript, world)
    system_calls = [call for turn in transcript.turns for call in turn.llm_calls]
    roles = {"system": len(system_calls), "user": len(user_calls)}
    return CaseResult(
        run_id=run_id,
        system=system.name,
        run_index=run_index,
        model_label=system.model_label,
        scenario_id=scenario.id,
        split=scenario.split.value,
        workflow=scenario.workflow.value if scenario.workflow else None,
        category=scenario.category.value,
        language=scenario.language.value,
        dialect=scenario.dialect.value,
        segment=segment_of(scenario, world),
        tags=list(scenario.tags),
        in_scope=scenario.in_scope,
        expected_outcome=scenario.expected_outcome.value,
        mode=scenario.mode.value,
        driver=driver,
        review_status=scenario.review_status.value,
        transcript=transcript,
        grade=graded,
        latency_ms=sum(turn.latency_ms for turn in transcript.turns),
        cost_usd=sum((call.cost_usd for call in system_calls), Decimal(0)),
        input_tokens=sum(call.input_tokens for call in system_calls),
        output_tokens=sum(call.output_tokens for call in system_calls),
        model_calls=roles,
    )


def read_results(path: Path) -> list[CaseResult]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [CaseResult.model_validate_json(line) for line in lines if line.strip()]


def append_result(path: Path, result: CaseResult) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(result.model_dump_json() + "\n")


def done_keys(results: Iterable[CaseResult]) -> set[tuple[str, int, str]]:
    return {(r.system, r.run_index, r.scenario_id) for r in results}


async def run_cases(
    systems: Mapping[str, SystemUnderTest],
    plan: Sequence[tuple[str, int, Scenario]],
    world: World,
    *,
    run_id: str,
    out_dir: Path,
    simulator: SimulatedUser | None,
    resume: bool = False,
) -> list[CaseResult]:
    """Play every ``(system, run index, scenario)`` of ``plan``, appending each result as it finishes."""
    path = out_dir / RESULTS
    existing = read_results(path) if resume else []
    if not resume and path.exists():
        path.unlink()
    skip = done_keys(existing)
    results = list(existing)
    for number, (name, run_index, scenario) in enumerate(plan, start=1):
        if (name, run_index, scenario.id) in skip:
            continue
        result = await play_case(
            systems[name], scenario, world, run_id=run_id, run_index=run_index, simulator=simulator
        )
        append_result(path, result)
        results.append(result)
        LOGGER.info(
            "%d/%d %s run %d %s: %s",
            number,
            len(plan),
            name,
            run_index,
            scenario.id,
            result.grade.final_outcome if result.grade else "harness error",
        )
    return results


def dump_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
