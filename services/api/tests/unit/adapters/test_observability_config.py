"""The provisioned alert rules and dashboard query only metrics the service emits (the instrument catalog)."""

import json
import re
from pathlib import Path

import pytest
import yaml

from bank_agent.adapters.telemetry.catalog import CATALOG, Kind

OBSERVABILITY = Path(__file__).resolve().parents[5] / "deploy" / "observability"
DASHBOARDS = OBSERVABILITY / "grafana" / "provisioning" / "dashboards"
EXTERNAL = ("http_server_",)
"""Metrics from the OpenTelemetry FastAPI instrumentation, not from the catalog."""


def prometheus_names() -> dict[str, str]:
    """Each catalog instrument under the names the collector's Prometheus exporter gives it."""
    names: dict[str, str] = {}
    for name, instrument in CATALOG.items():
        base = name.replace(".", "_")
        if instrument.unit == "s":
            base += "_seconds"
        if instrument.kind is Kind.COUNTER:
            names[base + "_total"] = name
        elif instrument.kind is Kind.HISTOGRAM:
            for suffix in ("_bucket", "_sum", "_count"):
                names[base + suffix] = name
        else:
            names[base] = name
    return names


def queried(expressions: list[str]) -> set[str]:
    found: set[str] = set()
    for expression in expressions:
        found |= set(re.findall(r"\b(?:bank|gen_ai|http_server)_[a-z0-9_]+\b", expression))
    return {name for name in found if not name.startswith(("bank_workflow", "bank_llm_model", "bank_component"))}


def alert_expressions() -> list[str]:
    rules = yaml.safe_load((OBSERVABILITY / "alerts.yml").read_text(encoding="utf-8"))
    return [rule["expr"] for group in rules["groups"] for rule in group["rules"]]


def dashboard_expressions() -> list[str]:
    expressions: list[str] = []
    for path in sorted(DASHBOARDS.glob("*.json")):
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        expressions.extend(target["expr"] for panel in dashboard["panels"] for target in panel.get("targets", []))
    return expressions


LABELS = {
    "bank_workflow_from", "bank_llm_budget_cap", "bank_intervention", "bank_escalation_reason", "bank_tool_status",
    "bank_tool", "bank_outcome", "bank_detector", "bank_credit_product", "bank_eligibility_outcome", "bank_prompt_id",
    "bank_rate_class", "bank_rate_key", "bank_language", "gen_ai_request_model", "gen_ai_response_model",
    "gen_ai_token_type",
}  # fmt: skip


@pytest.mark.parametrize("source", [alert_expressions, dashboard_expressions])
def test_every_queried_metric_is_emitted(source: object) -> None:
    names = prometheus_names()
    expressions = source()  # type: ignore[operator]
    unknown = sorted(
        name for name in queried(expressions) - LABELS if name not in names and not name.startswith(EXTERNAL)
    )
    assert unknown == []


def test_every_alert_links_its_runbook_section() -> None:
    runbook = (OBSERVABILITY.parents[1] / "docs" / "operations" / "runbook.md").read_text(encoding="utf-8").lower()
    rules = yaml.safe_load((OBSERVABILITY / "alerts.yml").read_text(encoding="utf-8"))
    for group in rules["groups"]:
        for rule in group["rules"]:
            anchor = rule["annotations"]["runbook"].split("#")[1]
            assert anchor == rule["alert"].lower()
            assert f"## {rule['alert'].lower()}" in runbook
