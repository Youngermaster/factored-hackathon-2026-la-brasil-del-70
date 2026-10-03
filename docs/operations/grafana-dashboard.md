# Grafana dashboards

Grafana is the live administrative observability surface. It is provisioned from version-controlled JSON, uses
Prometheus as its only metric source, and contains no customer identifiers, message text, document numbers, account
amounts, credit profiles, or risk estimates. The service emits the bounded labels documented in the
[signal catalog](observability.md#signal-catalog) through OpenTelemetry; the collector converts them to Prometheus
series, and Grafana queries those series. [ADR 0036](../adr/0036-grafana-live-analytics-separate-from-offline-evaluation.md)
records why live Grafana telemetry and offline evaluation evidence remain separate.

Two read-only dashboards are provisioned in the **Bank agent** folder:

| Dashboard | UID | Purpose |
|---|---|---|
| Bank agent: executive analytics | `bank-agent-executive` | Live demand, outcomes, escalation, safety, tool, model, and HTTP indicators for an administrator |
| Bank agent: reliability and operations | `bank-agent-overview` | Detailed diagnosis of dependencies, workflow routing, tools, the model gateway, and service health |

The executive dashboard defaults to the last 24 hours and refreshes every 30 seconds. Its **Workflow** and
**Language** variables support one, several, or all values. Language filters apply only to turn metrics because the
other instruments deliberately do not carry language labels. Grafana's global time picker changes every period
total and time series.

## Executive dashboard fields

Every period total uses Prometheus `increase` over Grafana's selected `$__range`; rate charts use
`$__rate_interval`. Empty counters display zero where zero is meaningful. Percentages protect against an empty
denominator with `clamp_min(..., 1)`.

| Section and field | Prometheus source | Calculation and interpretation |
|---|---|---|
| Workflow | `bank_turn_outcomes_total.bank_workflow` | Multi-select filter populated from observed workflow labels |
| Language | `bank_turn_outcomes_total.bank_language` | Multi-select filter populated from detected language labels, including `unknown` when detection was unavailable |
| Turns in selected period | `bank_turn_outcomes_total` | Sum of counter increases for the selected workflow and language |
| Resolved turn share | `bank_turn_outcomes_total` | `resolved turns / all turns * 100`; an operational terminal outcome, not the evaluation harness's safe automated resolution metric |
| Escalated turn share | `bank_turn_outcomes_total` | `escalated turns / all turns * 100` for the same filters |
| Turn latency p95 | `bank_turn_duration_seconds_bucket` | Histogram 95th percentile across the selected period and workflow; the histogram does not have a language label |
| Safety interventions | `bank_safety_interventions_total` | Count of deterministic safeguards applied by the engine |
| Active sessions | `bank_sessions_active` | Maximum reported gauge across workers; the backing session store is shared |
| Turn volume by workflow | `bank_turn_outcomes_total` | Period turn count grouped by workflow, with the language filter applied |
| Outcome rate over time | `bank_turn_outcomes_total` | Per-second rate grouped by workflow and outcome; outcomes are `resolved`, `clarified`, `abstained`, `escalated`, `refused`, and `in_progress` |
| Language mix | `bank_turn_outcomes_total` | Period turn count grouped by detected language |
| Escalations by workflow and reason | `bank_escalations_total` | Created handoffs grouped by workflow and reason code; this can differ from escalated-turn count because it measures the handoff artifact |
| Safety interventions by code | `bank_safety_interventions_total` | Period count grouped by workflow and intervention code |
| Unsafe responses blocked | `bank_safety_unsafe_blocked_total` | Messages rejected before customer delivery by a grounding detector |
| Tool calls by status | `bank_tool_calls_total` | Period calls grouped by tool and final record status: `ok`, `not_found`, `failed`, `unknown`, or `rejected_by_allowlist` |
| Tool latency p95 | `bank_tool_duration_seconds_bucket` | Rolling 95th percentile by tool, including retries |
| Model fallback calls | `bank_llm_fallbacks_total` | Calls replaced by a deterministic path, filtered by workflow |
| Known model cost | `bank_llm_cost_usd_sum` | Sum of known USD cost for successful model calls; unpriced calls are not silently estimated |
| HTTP request rate by status | `http_server_request_duration_seconds_count` | Per-second request rate grouped by response status code |
| HTTP latency p95 by route | `http_server_request_duration_seconds_bucket` | Rolling server-latency 95th percentile grouped by normalized route, never raw URLs |
| Rate-limit rejections | `bank_http_rate_limited_total` | Period count of requests refused by shared rate limits |
| Degradation level | `bank_degradation_level` | Maximum across workers: 0 normal, 1 fallback provider, 2 template only, 3 rule baselines, 4 database unavailable |

## What remains in the web console

The evaluator-only `/console/dashboard` is intentionally retained. It reads versioned, published evaluation
summaries and compares systems on a frozen synthetic workload. Grafana instead reports live telemetry from the
running deployment. Combining the two sources would make an offline benchmark look like production behavior, so
they remain separate and visibly labeled:

| Surface | Measurement | Source | Retention |
|---|---|---|---|
| Grafana | Live operational telemetry | OpenTelemetry to Prometheus | 7 days in development, 15 days or 2 GB in production |
| Web administrative dashboard | Offline, simulated, or projected evaluation | `GET /v1/eval/summaries` | Published summary artifacts |

## Access

Local development:

```bash
make up PROFILES=obs
make api-obs
```

Open `http://localhost:3000/d/bank-agent-executive` for the executive dashboard or
`http://localhost:3000/d/bank-agent-overview` for reliability and operations. Local Grafana has anonymous viewer
access and binds only to loopback.

Production enables the observability profile with `OBS=1 deploy/prod.sh up`. Grafana binds only to server loopback,
disables anonymous access, and requires its admin password. Create the SSH tunnel documented in
[the deployment guide](../../deploy/README.md#operate), then use the same local URLs. Do not expose port 3000 in the
public firewall and do not embed authenticated Grafana in the customer web application.

## Provisioning and change control

Dashboard JSON lives under `deploy/observability/grafana/provisioning/dashboards/`. Grafana loads every JSON file in
that directory as read-only, so durable changes are reviewed in Git rather than edited in the UI. The Prometheus
datasource has stable UID `prometheus` in both development and production.

`test_observability_config.py` parses every provisioned dashboard and fails if a query references a project metric
outside the telemetry catalog. JSON parsing, Compose rendering, and a live Grafana provisioning check are the
appropriate verification steps after a dashboard change.

## Limitations

- Prometheus retention bounds the available history. The dashboard is not a warehouse or an audit ledger.
- Counter increases can be approximate at range boundaries and can briefly show fractional values after Prometheus
  extrapolation, even though the underlying events are discrete.
- A resolved turn does not prove policy-compliant automation. Use the published evaluation dashboard for safe
  automated resolution, containment, confidence intervals, and population slices.
- Cost includes only calls with a configured price basis and is not a financial ledger.
- Metrics have bounded technical labels only. Investigate a specific conversation through its execution record and
  trace ID, not through Grafana.
