"""The provisioned alert rules and dashboard query only metrics the service emits (the instrument catalog)."""

import json
import re
from pathlib import Path
from typing import Any

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


COLLECTOR: dict[str, Any] = yaml.safe_load((OBSERVABILITY / "otel-collector.yaml").read_text(encoding="utf-8"))
CLIENT_IDENTIFIERS = {"client.address", "client.port", "user_agent.original"}
"""Span attributes the ASGI instrumentation records about the caller; none may be stored (ADR 0045)."""


def test_the_collector_drops_client_addresses_and_user_agents_before_anything_is_stored() -> None:
    privacy = COLLECTOR["processors"]["attributes/privacy"]["actions"]
    deleted = {action["key"] for action in privacy if action["action"] == "delete"}
    assert deleted >= CLIENT_IDENTIFIERS
    for pipeline in ("traces", "metrics"):
        processors = COLLECTOR["service"]["pipelines"][pipeline]["processors"]
        assert "attributes/privacy" in processors
        assert processors[0] == "memory_limiter"
        assert processors[-1] == "batch"


def test_a_stopped_workers_series_expire_within_five_minutes() -> None:
    """Workers export every 15 s; a dead worker's last value must not linger in max() panels and alerts."""
    assert COLLECTOR["exporters"]["prometheus"]["metric_expiration"] == "5m"


def test_host_metrics_reach_prometheus_without_network_counters() -> None:
    """/proc/net/dev inside the container describes the container's interface, not the VM's."""
    receiver = COLLECTOR["receivers"]["host_metrics"]
    assert set(receiver["scrapers"]) == {"cpu", "load", "memory", "disk", "filesystem"}
    assert receiver["scrapers"]["filesystem"]["include_mount_points"]["mount_points"] == ["/"]
    assert "host_metrics" in COLLECTOR["service"]["pipelines"]["metrics"]["receivers"]
    assert "host_metrics" not in COLLECTOR["service"]["pipelines"]["traces"]["receivers"]


def test_grafana_offers_only_prometheus_and_deletes_the_jaeger_datasource() -> None:
    """Anonymous or signed-in viewers must not read traces through Grafana's datasource proxy."""
    path = OBSERVABILITY / "grafana" / "provisioning" / "datasources" / "datasources.yaml"
    provisioning = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert [(source["name"], source["type"]) for source in provisioning["datasources"]] == [("Prometheus", "prometheus")]
    assert provisioning["datasources"][0]["uid"] == "prometheus"
    assert provisioning["datasources"][0]["editable"] is False
    assert {"name": "Jaeger", "orgId": 1} in provisioning["deleteDatasources"]
