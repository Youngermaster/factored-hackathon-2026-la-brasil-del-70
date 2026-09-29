"""The stratified subset of scenarios repeated for pass^k and between-run variance (the plan's 48 on test).

Per workflow: 3 normal, 2 ambiguous, 1 unsupported, 2 human_required, 1 missing or incorrect data, 1 prompt
injection, 1 tool failure, and 1 unauthorized access or expired session; within each quota the scenarios
alternate Spanish and Portuguese, in id order, so the choice is deterministic and crosses both languages.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from bank_evals.scenarios.mix import ROUTING_TAG, WORKFLOWS
from bank_evals.scenarios.model import Scenario, ScenarioCategory

C = ScenarioCategory
QUOTAS: Final = (
    ({C.NORMAL}, 3), ({C.AMBIGUOUS}, 2), ({C.UNSUPPORTED}, 1), ({C.HUMAN_REQUIRED}, 2),
    ({C.MISSING_OR_INCORRECT_DATA}, 1), ({C.PROMPT_INJECTION}, 1), ({C.TOOL_FAILURE}, 1),
    ({C.UNAUTHORIZED_ACCESS, C.EXPIRED_SESSION}, 1),
)  # fmt: skip


def _alternating(items: Sequence[Scenario], count: int) -> list[Scenario]:
    spanish = [s for s in items if s.language.value == "es"]
    portuguese = [s for s in items if s.language.value == "pt"]
    chosen: list[Scenario] = []
    while len(chosen) < count and (spanish or portuguese):
        for pool in (spanish, portuguese):
            if pool and len(chosen) < count:
                chosen.append(pool.pop(0))
    return chosen


def variance_subset(scenarios: Sequence[Scenario]) -> list[Scenario]:
    ordered = sorted((s for s in scenarios if ROUTING_TAG not in s.tags), key=lambda s: s.id)
    chosen: list[Scenario] = []
    for workflow in WORKFLOWS:
        mine = [s for s in ordered if s.workflow is workflow]
        for categories, count in QUOTAS:
            chosen += _alternating([s for s in mine if s.category in categories], count)
    return chosen
