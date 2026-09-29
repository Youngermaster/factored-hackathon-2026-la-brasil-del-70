"""Project a run's model calls, wall clock, and cost from a measured run (the plan's feasibility check).

Calls run one at a time on the local model, so the wall clock is the number of calls times the mean latency per
call. Model calls per case are measured per system (P and B1 from their records, the simulated user from its own
calls on simulated scenarios); the judge is one call per transcript. The cost prices the measured mean tokens per
call with the dated price table (projected, never measured).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from statistics import mean
from typing import Any

from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.domain.intelligence import TokenUsage
from bank_evals.graders.model import CaseResult

SYSTEMS_WITH_MODEL = ("p", "b1")
SIMULATED_BY = ("b0", "p", "b1")


def _calls(results: Sequence[CaseResult], system: str) -> list[Any]:
    return [call for r in results if r.system == system for t in r.transcript.turns for call in t.llm_calls]


def estimate_run(
    results: Sequence[CaseResult],
    *,
    scenarios: int,
    simulated: int,
    judge_sample: int,
    prices: PriceTable,
    price_model: str | None,
) -> dict[str, Any]:
    ok_calls = [c for s in SYSTEMS_WITH_MODEL for c in _calls(results, s) if c.status == "ok"]
    per_case = {}
    for system in SYSTEMS_WITH_MODEL:
        cases = [r for r in results if r.system == system]
        per_case[system] = len(_calls(results, system)) / len(cases) if cases else 0.0
    simulated_cases = [r for r in results if r.mode == "simulated" and r.driver == "simulated"]
    user_per_case = mean(r.model_calls.get("user", 0) for r in simulated_cases) if simulated_cases else 0.0
    user_calls = [c for r in simulated_cases for c in r.transcript.user_calls if c.status == "ok"]
    ok_calls = ok_calls + user_calls
    latency_ms = mean(c.latency_ms for c in ok_calls) if ok_calls else None
    by_role = {
        "p": [c.latency_ms for c in _calls(results, "p") if c.status == "ok"],
        "b1": [c.latency_ms for c in _calls(results, "b1") if c.status == "ok"],
        "user": [c.latency_ms for c in user_calls],
    }
    projected = {
        "p_calls": round(per_case["p"] * scenarios),
        "b1_calls": round(per_case["b1"] * scenarios),
        "simulator_calls": round(user_per_case * simulated * len(SIMULATED_BY)),
        "judge_calls": judge_sample * len(SIMULATED_BY),
    }
    total = sum(projected.values())
    role_latency = {role: mean(v) if v else latency_ms for role, v in by_role.items()}
    weighted_ms = None
    if latency_ms is not None:
        weighted_ms = (
            projected["p_calls"] * (role_latency["p"] or latency_ms)
            + projected["b1_calls"] * (role_latency["b1"] or latency_ms)
            + projected["simulator_calls"] * (role_latency["user"] or latency_ms)
            + projected["judge_calls"] * latency_ms
        )
    out: dict[str, Any] = {
        "measured_cases": len(results),
        "measured_calls": len(ok_calls),
        "mean_latency_per_call_ms": round(latency_ms) if latency_ms is not None else None,
        "calls_per_case": {k: round(v, 2) for k, v in per_case.items()},
        "mean_latency_ms_by_role": {role: round(mean(v)) if v else None for role, v in by_role.items()},
        "simulator_calls_per_simulated_case": round(user_per_case, 2),
        **projected,
        "total_calls": total,
        "projected_wall_clock_hours": round(weighted_ms / 3_600_000, 2) if weighted_ms is not None else None,
    }
    if price_model and ok_calls:
        usage = TokenUsage(
            input_tokens=round(mean(c.input_tokens for c in ok_calls)),
            output_tokens=round(mean(c.output_tokens for c in ok_calls)),
        )
        per_call = prices.cost(price_model, usage)
        out["price_model"] = price_model
        out["projected_cost_usd"] = str((per_call * total).quantize(Decimal("0.01")))
        out["cost_label"] = "projected from measured mean tokens per call and the dated price table"
    return out
