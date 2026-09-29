"""Markdown tables for the evaluation reports: rates with Wilson intervals, zero-event bounds, small cells."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from bank_evals.metrics.aggregate import SMALL_CELL
from bank_evals.metrics.stats import clopper_pearson, wilson, zero_event_bounds

NOT_DEFINED = "not defined"


def rate(block: dict[str, Any]) -> str:
    """``count/denominator (rate%, Wilson 95% low to high)``, or "not defined" for an empty denominator."""
    count, n = block["count"], block["denominator"]
    interval = wilson(count, n)
    if interval is None:
        return f"0/0 ({NOT_DEFINED})"
    return f"{count}/{n} ({100 * count / n:.0f}%, {100 * interval.low:.0f} to {100 * interval.high:.0f})"


def unsafe_rate(block: dict[str, Any]) -> str:
    """Unsafe outcomes: counts with the exact interval; with zero events, the rule of three and the exact bound."""
    count, n = block["count"], block["denominator"]
    bounds, interval = zero_event_bounds(n), clopper_pearson(count, n)
    if bounds is None or interval is None:
        return f"0/0 ({NOT_DEFINED})"
    if count == 0:
        return (
            f"0/{n} (95% upper bound {100 * bounds.exact_upper_95:.1f}%; "
            f"rule of three {100 * bounds.rule_of_three:.1f}%)"
        )
    return f"{count}/{n} ({100 * count / n:.1f}%, exact 95% {100 * interval.low:.1f} to {100 * interval.high:.1f})"


def money(value: str | None) -> str:
    return NOT_DEFINED if value is None else f"{value} USD"


def ms(value: int | None) -> str:
    return "n/a" if value is None else f"{value} ms"


def cell(block: dict[str, Any]) -> str:
    flag = " (small)" if block["cases"] < SMALL_CELL else ""
    return f"{block['cases']}{flag}"


METRIC_ROWS: tuple[tuple[str, str], ...] = (
    ("Cases (in scope)", "cases"),
    ("Safe automated resolution", "safe_automated_resolution"),
    ("Automation attempted", "automation_attempted"),
    ("Containment", "containment"),
    ("Missed transfers", "escalation_missed"),
    ("Unnecessary transfers", "escalation_unnecessary"),
    ("Handoff completeness", "handoff_complete"),
    ("Unsafe outcomes", "unsafe_outcomes"),
    ("Task success", "task_success"),
    ("Policy compliance", "policy_compliant"),
    ("Routing correct", "routing_correct"),
    ("Language correct", "language_correct"),
    ("Latency per turn p50 / p95", "latency"),
    ("Cost per attempted case", "cost_per_attempted_case_usd"),
    ("Cost per safe automated resolution", "cost_per_resolution_usd"),
)


def value(block: dict[str, Any], key: str) -> str:
    if key == "cases":
        return cell(block)
    if key == "unsafe_outcomes":
        return unsafe_rate(block[key])
    if key == "latency":
        return f"{ms(block['latency_turn_p50_ms'])} / {ms(block['latency_turn_p95_ms'])}"
    if key.startswith("cost"):
        return money(block[key])
    return rate(block[key])


def metrics_table(columns: Sequence[tuple[str, dict[str, Any]]]) -> list[str]:
    """One row per metric, one column per system (or slice)."""
    header = "| Metric | " + " | ".join(name for name, _ in columns) + " |"
    lines = [header, "|---|" + "---|" * len(columns)]
    for label, key in METRIC_ROWS:
        lines.append(f"| {label} | " + " | ".join(value(block, key) for _, block in columns) + " |")
    return lines


def unsafe_types_table(columns: Sequence[tuple[str, dict[str, Any]]]) -> list[str]:
    kinds = sorted({kind for _, block in columns for kind in block["unsafe_by_type"]})
    lines = [
        "| Unsafe outcome type | " + " | ".join(name for name, _ in columns) + " |",
        "|---|" + "---|" * len(columns),
    ]
    for kind in kinds:
        cells = [unsafe_rate(block["unsafe_by_type"][kind]) for _, block in columns]
        lines.append(f"| {kind.replace('_', ' ')} | " + " | ".join(cells) + " |")
    return lines
