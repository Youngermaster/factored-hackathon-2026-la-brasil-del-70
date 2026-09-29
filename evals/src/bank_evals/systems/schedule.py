"""Which call of which tool fails, over one case (``tool_failure_plan``); shared by P, B0, and B1.

This module imports only the domain and the scenario contract, so baseline B1 can use it without reaching the
application layer (an import-linter contract).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from bank_agent.domain.actions import ToolFailureMode
from bank_evals.scenarios.model import ToolFailureStep


class FailureSchedule:
    """Counts calls per tool over one case and says which call fails, and how."""

    def __init__(self, plan: Sequence[ToolFailureStep]) -> None:
        self._plan = tuple(plan)
        self.calls: Counter[str] = Counter()
        self.injected: list[tuple[str, str]] = []

    def next_mode(self, tool: str) -> ToolFailureMode | None:
        self.calls[tool] += 1
        count = self.calls[tool]
        for step in self._plan:
            if step.tool.value == tool and step.on_call <= count < step.on_call + step.times:
                self.injected.append((tool, step.mode.value))
                return step.mode
        return None
