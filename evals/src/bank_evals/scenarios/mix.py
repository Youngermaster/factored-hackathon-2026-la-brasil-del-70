"""The scenario mix of the evaluation plan (``docs/evaluation/plan.md``): scenarios per workflow and category, per
split, the routing scenarios, the language split, and the categories the simulated user plays."""

from __future__ import annotations

from typing import Final

from bank_agent.domain.locale import Locale
from bank_agent.domain.workflow import WorkflowId
from bank_evals.scenarios.model import ScenarioCategory, Split

C = ScenarioCategory
WORKFLOWS: Final = (WorkflowId.ACCOUNT_INQUIRY, WorkflowId.CARD_SUPPORT, WorkflowId.DISPUTE, WorkflowId.CREDIT)
PER_WORKFLOW: Final[dict[Split, dict[ScenarioCategory, int]]] = {
    Split.TEST: {
        C.NORMAL: 18, C.AMBIGUOUS: 12, C.UNSUPPORTED: 6, C.HUMAN_REQUIRED: 10, C.MISSING_OR_INCORRECT_DATA: 6,
        C.EXPIRED_SESSION: 4, C.UNAUTHORIZED_ACCESS: 6, C.PROMPT_INJECTION: 8, C.TOOL_FAILURE: 6,
    },
    Split.DEV: {
        C.NORMAL: 6, C.AMBIGUOUS: 4, C.UNSUPPORTED: 2, C.HUMAN_REQUIRED: 4, C.MISSING_OR_INCORRECT_DATA: 2,
        C.EXPIRED_SESSION: 2, C.UNAUTHORIZED_ACCESS: 2, C.PROMPT_INJECTION: 4, C.TOOL_FAILURE: 2,
    },
}  # fmt: skip
ROUTING: Final[dict[Split, dict[str, int]]] = {
    Split.TEST: {"out_of_scope": 16, "switch": 12},
    Split.DEV: {"out_of_scope": 6, "switch": 4},
}
PORTUGUESE_SHARE: Final = 0.4
SPANISH_DIALECTS: Final = (Locale.ES_MX, Locale.ES_CO, Locale.ES_AR)
SIMULATED_CATEGORIES: Final = frozenset({C.AMBIGUOUS})
"""Every ambiguous scenario is simulated; so is every direct prompt injection (tag ``direct``)."""
DIRECT_INJECTION_TAG: Final = "direct"
ROUTING_TAG: Final = "routing"


def language_plan(count: int) -> list[Locale]:
    """``count`` dialects: 40% pt-BR (rounded), the rest split evenly over es-MX, es-CO, es-AR, interleaved."""
    portuguese = round(count * PORTUGUESE_SHARE)
    if count >= 2 and portuguese == 0:
        portuguese = 1
    if count >= 2 and portuguese == count:
        portuguese = count - 1
    spanish = [SPANISH_DIALECTS[i % len(SPANISH_DIALECTS)] for i in range(count - portuguese)]
    plan: list[Locale] = []
    while spanish or portuguese:
        if spanish:
            plan.append(spanish.pop(0))
        if portuguese:
            plan.append(Locale.PT_BR)
            portuguese -= 1
    return plan


def total(split: Split) -> int:
    return len(WORKFLOWS) * sum(PER_WORKFLOW[split].values()) + sum(ROUTING[split].values())
