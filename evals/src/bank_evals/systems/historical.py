"""H: the historical reference per workflow, from the phase 04 analysis (``docs/analysis/analysis-results.json``).

H is never scored on scenarios. Its numbers are measured on the organizer's historical interactions (synthetic
data, offline), with the phase 04 contact-reason mapping, so they describe how human agents handled that traffic,
not the evaluation workload. Costs are projections under the unverified team assumptions of phase 04.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from bank_evals.meta import REPOSITORY_ROOT

ANALYSIS_RESULTS: Final = REPOSITORY_ROOT / "docs" / "analysis" / "analysis-results.json"
WORKFLOWS: Final = ("account_inquiry", "card_support", "dispute", "credit")
LABEL: Final = "historical, offline, organizer data (synthetic); reference only, not scored on scenarios"


@dataclass(frozen=True)
class HistoricalReference:
    workflow: str
    interactions: int
    first_contact_resolution: float
    escalation_rate: float
    handle_time_seconds: float
    wait_time_seconds: float
    csat_low_share: float
    cost_per_resolved_contact_usd: float | None
    """Projected at the assumption scenario 1.0 (unverified team cost assumptions)."""


def _estimate(block: dict[str, Any], key: str) -> float:
    return float(block[key]["estimate"])


def load_historical(path: Path = ANALYSIS_RESULTS) -> dict[str, HistoricalReference]:
    """The reference per workflow; an empty mapping when the analysis file is missing."""
    if not path.is_file():
        return {}
    results = json.loads(path.read_text(encoding="utf-8"))["results"]
    out: dict[str, HistoricalReference] = {}
    for workflow in WORKFLOWS:
        outcome = results["outcomes"][workflow]
        costs = results.get("costs", {}).get("workflows", {}).get(workflow, {})
        projected = costs.get("scenarios", {}).get("1", {}).get("cost_per_resolved_contact")
        out[workflow] = HistoricalReference(
            workflow=workflow,
            interactions=int(outcome["interactions"]),
            first_contact_resolution=_estimate(outcome, "first_contact_resolution"),
            escalation_rate=_estimate(outcome, "escalation"),
            handle_time_seconds=_estimate(outcome, "handle_time_seconds"),
            wait_time_seconds=_estimate(outcome, "wait_time_seconds"),
            csat_low_share=_estimate(outcome, "csat_low_share"),
            cost_per_resolved_contact_usd=float(projected) if projected is not None else None,
        )
    return out


def historical_table(references: dict[str, HistoricalReference]) -> list[str]:
    lines = [
        "| Workflow | Interactions | First contact resolution | Escalated | Handle time | Wait time | CSAT 1 or 2 "
        "| Cost per resolved contact (projected) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for ref in references.values():
        cost = "n/a" if ref.cost_per_resolved_contact_usd is None else f"{ref.cost_per_resolved_contact_usd:.2f} USD"
        lines.append(
            f"| `{ref.workflow}` | {ref.interactions:,} | {100 * ref.first_contact_resolution:.1f}% | "
            f"{100 * ref.escalation_rate:.1f}% | {ref.handle_time_seconds:.0f} s | {ref.wait_time_seconds:.0f} s | "
            f"{100 * ref.csat_low_share:.1f}% | {cost} |"
        )
    return lines
