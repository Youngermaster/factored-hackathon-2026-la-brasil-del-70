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
EXTERNAL = frozenset({
    "http_server_request_duration_seconds_bucket", "http_server_request_duration_seconds_count",
    "http_server_request_duration_seconds_sum", "http_server_active_requests", "db_client_connections_usage",
    "system_cpu_time_seconds_total", "system_cpu_load_average_1m", "system_cpu_load_average_5m",
    "system_cpu_load_average_15m", "system_memory_utilization_ratio", "system_filesystem_utilization_ratio",
})  # fmt: skip
"""Metrics from the FastAPI and SQLAlchemy instrumentations and the collector's host_metrics receiver, not from the
catalog, under the names the 0.161.0 collector exports (checked against its Prometheus endpoint)."""
METRIC = re.compile(r"\b(?:bank|gen_ai|http_server|http_client|db_client|system)_[a-z0-9_]+\b")


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
        found |= set(METRIC.findall(expression))
    return {name for name in found if not name.startswith(("bank_workflow", "bank_llm_model", "bank_component"))}


def alert_expressions() -> list[str]:
    rules = yaml.safe_load((OBSERVABILITY / "alerts.yml").read_text(encoding="utf-8"))
    return [rule["expr"] for group in rules["groups"] for rule in group["rules"]]


def dashboards() -> dict[str, dict[str, Any]]:
    return {path.name: json.loads(path.read_text(encoding="utf-8")) for path in sorted(DASHBOARDS.glob("*.json"))}


def panels_of(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    """Every panel, including those nested in collapsed rows."""
    found: list[dict[str, Any]] = []
    pending = list(dashboard["panels"])
    while pending:
        panel = pending.pop(0)
        found.append(panel)
        pending.extend(panel.get("panels", []))
    return found


def dashboard_expressions() -> list[str]:
    expressions: list[str] = []
    for dashboard in dashboards().values():
        expressions.extend(target["expr"] for panel in panels_of(dashboard) for target in panel.get("targets", []))
        for variable in dashboard.get("templating", {}).get("list", []):
            query = variable.get("query")
            expressions.append(query["query"] if isinstance(query, dict) else str(query or ""))
    return expressions


LABELS = {
    "bank_workflow_from", "bank_llm_budget_cap", "bank_intervention", "bank_escalation_reason", "bank_tool_status",
    "bank_tool", "bank_outcome", "bank_detector", "bank_credit_product", "bank_eligibility_outcome", "bank_prompt_id",
    "bank_rate_class", "bank_rate_key", "bank_language", "gen_ai_request_model", "gen_ai_response_model",
    "gen_ai_token_type", "bank_llm_price_basis",
}  # fmt: skip


@pytest.mark.parametrize("source", [alert_expressions, dashboard_expressions])
def test_every_queried_metric_is_emitted(source: object) -> None:
    names = prometheus_names()
    expressions = source()  # type: ignore[operator]
    unknown = sorted(name for name in queried(expressions) - LABELS if name not in names and name not in EXTERNAL)
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
    sources = [(source["name"], source["type"]) for source in provisioning["datasources"]]
    assert sources == [("Prometheus", "prometheus")]
    assert provisioning["datasources"][0]["uid"] == "prometheus"
    assert provisioning["datasources"][0]["editable"] is False
    assert {"name": "Jaeger", "orgId": 1} in provisioning["deleteDatasources"]


def test_every_dashboard_is_read_only_prometheus_only_and_uniquely_identified() -> None:
    boards = dashboards()
    assert set(boards) == {"bank-agent.json", "bank-agent-executive.json", "bank-agent-service.json"}
    assert len({board["uid"] for board in boards.values()}) == len(boards)
    for name, board in boards.items():
        assert board["editable"] is False, name
        panels = panels_of(board)
        assert len({panel["id"] for panel in panels}) == len(panels), name
        for panel in panels:
            if panel["type"] == "row":
                continue
            assert panel["datasource"] == {"type": "prometheus", "uid": "prometheus"}, (name, panel["title"])
            assert panel["targets"], (name, panel["title"])
            refs = [target["refId"] for target in panel["targets"]]
            assert len(set(refs)) == len(refs), (name, panel["title"])
        assert "jaeger" not in json.dumps(board).lower(), name


def test_category_panels_receive_one_value_per_series() -> None:
    """An instant query returns one frame per series; a bar chart needs one frame with a category field."""
    for name, board in dashboards().items():
        for panel in panels_of(board):
            if panel["type"] == "barchart":
                reducers = [step for step in panel.get("transformations", []) if step["id"] == "reduce"]
                tables = all(target.get("format") == "table" for target in panel["targets"])
                assert reducers or tables, (name, panel["title"])
            if panel["type"] == "bargauge":
                assert panel["options"]["reduceOptions"]["values"] is False, (name, panel["title"])
    executive = {panel["title"]: panel for panel in panels_of(dashboards()["bank-agent-executive.json"])}
    assert executive["Turn volume by workflow"]["type"] == "bargauge"


def test_counters_started_at_zero_do_not_fill_category_panels_with_empty_rows() -> None:
    """Outcome and handoff counters exist at 0 for every label set from startup; category panels keep only events."""
    for name, board in dashboards().items():
        for panel in panels_of(board):
            if panel["type"] not in {"bargauge", "piechart"}:
                continue
            for target in panel["targets"]:
                if "bank_turn_outcomes_total" in target["expr"] or "bank_escalations_total" in target["expr"]:
                    shares = "/ clamp_min(" in target["expr"]
                    assert shares or target["expr"].rstrip(" )").endswith("> 0"), (name, panel["title"])


def test_the_service_dashboard_answers_the_operating_questions() -> None:
    board = dashboards()["bank-agent-service.json"]
    assert board["uid"] == "bank-agent-service"
    assert board["title"] == "Bank agent: service health"
    panels = {panel["title"]: panel for panel in panels_of(board)}
    expressions = " ".join(target["expr"] for panel in panels.values() for target in panel.get("targets", []))
    for quantile in ("0.5", "0.95", "0.99"):
        assert f"histogram_quantile({quantile}, sum by (le, http_route)" in expressions
        assert f"histogram_quantile({quantile}, sum by (le, bank_workflow)" in expressions
    assert 'http_route="/v1/conversations/{conversation_id}/turns"' in expressions
    quota = panels["Tokens per minute against the quota"]["fieldConfig"]["defaults"]
    assert quota["custom"]["thresholdsStyle"]["mode"] == "line"
    assert [step["value"] for step in quota["thresholds"]["steps"]] == [None, 60000]
    for title in (
        "5xx share, last 5 minutes",
        "Model cost per turn",
        "Circuit state per model",
        "Degradation level over time",
        "Handoffs by reason",
        "Database connections in use",
        "CPU busy",
    ):
        assert title in panels
    level = panels["Degradation level"]["fieldConfig"]["defaults"]["mappings"][0]["options"]
    assert {key: value["text"].split()[0] for key, value in level.items()} == {str(n): f"L{n}" for n in range(5)}
    for panel in panels.values():
        if panel["type"] != "row":
            assert "not offline evaluation" in panel["description"], panel["title"]
