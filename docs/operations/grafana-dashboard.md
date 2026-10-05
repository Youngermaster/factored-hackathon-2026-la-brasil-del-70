# Grafana dashboards

Grafana is the live administrative observability surface. It is provisioned from version-controlled JSON, uses
Prometheus as its only metric source, and contains no customer identifiers, message text, document numbers, account
amounts, credit profiles, or risk estimates. The service emits the bounded labels documented in the
[signal catalog](observability.md#signal-catalog) through OpenTelemetry; the collector converts them to Prometheus
series, and Grafana queries those series. [ADR 0036](../adr/0036-grafana-live-analytics-separate-from-offline-evaluation.md)
records why live Grafana telemetry and offline evaluation evidence remain separate, and
[ADR 0045](../adr/0045-expose-grafana-read-only-under-grafana.md) why production serves Grafana read-only at
`/grafana/`.

Three read-only dashboards are provisioned in the **Bank agent** folder, linked to each other from their headers:

| Dashboard | UID | Purpose |
|---|---|---|
| Bank agent: service health | `bank-agent-service` | Grafana's home page: latency, errors, the model gateway, degradation, handoffs, the database pool, and the VM |
| Bank agent: executive analytics | `bank-agent-executive` | Live demand, outcomes, escalation, safety, tool, model, and HTTP indicators for an administrator |
| Bank agent: reliability and operations | `bank-agent-overview` | Detailed diagnosis of dependencies, workflow routing, tools, the model gateway, and service health |

## Open it

| Where | Address | Who |
|---|---|---|
| Production, public | <https://la-brasil-del-70.westus2.cloudapp.azure.com/grafana/> | With `GRAFANA_ANONYMOUS_VIEWER=true`, anyone, as a read-only Viewer; otherwise the admin login |
| Production, SSH tunnel | `http://localhost:3000/grafana/` after the tunnel in [the deployment guide](../../deploy/README.md#operate) | The admin; the break-glass path when the public route is off |
| Development | `http://localhost:3000/` after `make up PROFILES=obs` | Anonymous viewer on loopback |

The public route exists only when the server env file has `GRAFANA_ROUTE=on` and the `obs` profile runs (`OBS=1`).
A Viewer sees the provisioned dashboards and cannot edit or save them, open Explore, create snapshots, or share
public dashboards. Grafana's only datasource is Prometheus, so no trace can be read through Grafana.

**The anonymous viewer trade-off.** Judges open the dashboards without credentials, which is the point of exposing
them. In exchange, anyone can read live operational counts (including safety interventions, which hint at whether
injection attempts were caught) and send their own PromQL through the datasource, bounded by Prometheus's query
limits (30 s, 5 million samples, 4 concurrent queries). Every label is a bounded id or code from the
[signal catalog](observability.md#signal-catalog): no message text, amounts, identifiers, or traces. Setting
`GRAFANA_ANONYMOUS_VIEWER=false` and running `deploy/prod.sh up` returns to login-only; `GRAFANA_ROUTE=off` closes
the route entirely.

## Service health dashboard fields

Defaults: last 6 hours, refresh every 30 seconds, variables **Route** (`http_route`) and **Workflow**
(`bank_workflow`), both multi-select. Every panel description ends with "Live telemetry from the running service, not
offline evaluation." Rate panels use `$__rate_interval`; period panels use `increase` over `$__range`.

| Row and panel | Prometheus source | Calculation and interpretation |
|---|---|---|
| Service level: Requests per second | `http_server_request_duration_seconds_count` | Request rate for the selected routes; health probes are not instrumented |
| Service level: 5xx share, last 5 minutes | same | 5xx responses over all responses; yellow from 1 percent, red from 5 percent (the `ErrorRateSpike` alert) |
| Service level: p95 and p99 latency, last 5 minutes | `http_server_request_duration_seconds_bucket` | Histogram quantiles over 5 minutes; buckets reach 60 s, so a slow model call is measured instead of clamped at 10 s |
| Service level: Requests in flight | `http_server_active_requests` | Requests being processed now, summed over workers |
| Service level: Degradation level | `bank_degradation_level` | Highest level over workers, shown as L0 normal, L1 fallback model, L2 template only, L3 baselines, L4 database unavailable |
| HTTP: Latency p50, p95, p99 by route | `http_server_request_duration_seconds_bucket` | Quantiles per route template; path parameters are never labels |
| HTTP: Requests per second by status code | `http_server_request_duration_seconds_count` | Stacked rate by status code |
| HTTP: 5xx share by route | same | 5xx rate over all requests, per route; empty when no server error happened |
| HTTP: 4xx by route and status | same | Client errors: session and step-up checks, validation, customer isolation (another customer's resource answers 404), rate limits |
| HTTP: Rate-limit refusals | `bank_http_rate_limited_total` | Refusals by limit class and key kind (`ip` or `session`); the key itself is never a label |
| Turns: Engine turn latency p50, p95, p99 by workflow | `bank_turn_duration_seconds_bucket` | Engine time for a turn (routing, policy, tools, model calls); excludes the opening database reads and the closing write |
| Turns: End-to-end turn request p50, p95, p99 | `http_server_request_duration_seconds_bucket{http_route="/v1/conversations/{conversation_id}/turns"}` | What the customer waits for: engine time plus session checks, database I/O, and serialization. The gap to the engine panel is the platform overhead |
| Turns: Turns per minute by workflow and outcome | `bank_turn_outcomes_total` | Stacked rate of stored turns; zero series are hidden |
| Turns: Escalated share by workflow | same | Escalated turns over all turns in the period, per workflow; `router` counts turns before a workflow is chosen |
| Turns: Handoffs by reason | `bank_escalations_total` | Handoffs created in the period by reason code, largest first; reasons with no handoff are hidden |
| Model gateway: Model calls per minute by result | `gen_ai_client_operation_duration_seconds_count` | Logical calls (retries and failover inside one call) by `ok` or the error code that ended them |
| Model gateway: Model error share, last 15 minutes | same | Failed calls over all calls; a failed call falls back to deterministic templates and is never shown to the customer as an error |
| Model gateway: Successful call latency by serving model | `gen_ai_client_operation_duration_seconds_bucket{error_type=""}` | Quantiles of successful calls by the model that answered; failures are excluded so an open circuit does not pull the percentiles down |
| Model gateway: Tokens per minute against the quota | `gen_ai_client_token_usage_sum` | Input plus output tokens per minute by serving model, with a red line at 60,000, the production gpt-4.1-mini quota (gpt-4o has 50,000). Azure counts the requested maximum output against the quota, so throttling can begin below the line |
| Model gateway: Model calls per minute by serving model | `gen_ai_client_operation_duration_seconds_count{error_type=""}` | Calls served by the fallback model mean the primary failed (L1) |
| Model gateway: Model cost per turn, per resolved turn | `bank_llm_cost_usd_sum`, `bank_turn_outcomes_total` | Period model cost over stored turns, and over resolved turns (the brief's cost per successful resolution, as live telemetry) |
| Model gateway: Model calls per turn | `gen_ai_client_operation_duration_seconds_count`, `bank_turn_outcomes_total` | Deterministic paths make no call, so this shows how much of the traffic needs the model |
| Model gateway: Cost per hour by serving model and price basis | `bank_llm_cost_usd_sum` | Spend rate. `verified` is a checked list price; `unverified` and `unknown_model` are costed deliberately high (a safety multiplier, and for a model without a price row the highest known price) |
| Model gateway: Deterministic fallbacks by prompt and reason | `bank_llm_fallbacks_total` | Model calls replaced by templates or baselines: the reliability ladder working |
| Model gateway: Circuit state per model | `bank_llm_circuit_state` | State timeline: closed, half-open, open |
| Model gateway: Daily model budget used | `bank_llm_budget_daily_used_ratio` | Share of `LLM_DAILY_BUDGET_USD` spent today; at 1 the gateway refuses model calls |
| Dependencies: Degradation level over time | `bank_degradation_level` | State timeline of the highest level over workers |
| Dependencies: Component state | `bank_degradation_component` | State timeline per watched dependency: ok, degraded, unavailable, disabled |
| Dependencies: Database connections in use | `db_client_connections_usage{state="used"}` | Busiest worker and all workers; the red line is one worker's ceiling (5 pooled plus 5 overflow) |
| Dependencies: Database connection failures | `bank_database_unavailable_total` | Any value moves the service to L4 and fires `DatabaseUnavailable` |
| Host: CPU busy, Memory used, Load average, Root disk used | `system_cpu_time_seconds_total`, `system_memory_utilization_ratio`, `system_cpu_load_average_*`, `system_filesystem_utilization_ratio` | The VM, from the collector's `host_metrics` receiver reading its own `/proc` (not namespaced): no Docker socket or host mount. Per-container resources are not shown |

The executive dashboard defaults to the last 24 hours and refreshes every 30 seconds. Its **Workflow** and
**Language** variables support one, several, or all values. Language filters apply only to turn metrics because the
other instruments deliberately do not carry language labels. Grafana's global time picker changes every period
total and time series.

## Executive dashboard fields

Every period total uses Prometheus `increase` over Grafana's selected `$__range`; rate charts use
`$__rate_interval`. Empty counters display zero where zero is meaningful. Percentages protect against an empty
denominator with `clamp_min(..., 1)`. The outcome and handoff counters exist at zero for every workflow, outcome,
language, and reason from the moment a worker starts, so the first event after a deploy is counted; category panels
(bar gauges and the language pie) hide the zero series. The category panels are bar gauges because an instant
query returns one series per label set, which Grafana's bar chart cannot draw without a transformation (it rendered
empty before).

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
| Turn volume by workflow | `bank_turn_outcomes_total` | Period turn count grouped by workflow, with the language filter applied (a bar gauge: one bar per series) |
| Outcome rate over time | `bank_turn_outcomes_total` | Per-second rate grouped by workflow and outcome; outcomes are `resolved`, `clarified`, `abstained`, `escalated`, `refused`, and `in_progress` |
| Language mix | `bank_turn_outcomes_total` | Period turn count grouped by detected language |
| Escalations by workflow and reason | `bank_escalations_total` | Created handoffs grouped by workflow and reason code; this can differ from escalated-turn count because it measures the handoff artifact |
| Safety interventions by code | `bank_safety_interventions_total` | Period count grouped by workflow and intervention code |
| Unsafe responses blocked | `bank_safety_unsafe_blocked_total` | Messages rejected before customer delivery by a grounding detector |
| Tool calls by status | `bank_tool_calls_total` | Period calls grouped by tool and final record status: `ok`, `not_found`, `failed`, `unknown`, or `rejected_by_allowlist` |
| Tool latency p95 | `bank_tool_duration_seconds_bucket` | Rolling 95th percentile by tool, including retries |
| Model fallback calls | `bank_llm_fallbacks_total` | Calls replaced by a deterministic path, filtered by workflow |
| Known model cost | `bank_llm_cost_usd_sum` | Sum of USD cost for successful model calls; a model without a price row is costed at the highest known price times the safety multiplier and labelled `unknown_model` (see the service health dashboard) |
| HTTP request rate by status | `http_server_request_duration_seconds_count` | Per-second request rate grouped by response status code |
| HTTP latency p95 by route | `http_server_request_duration_seconds_bucket` | Rolling server-latency 95th percentile grouped by normalized route, never raw URLs |
| Rate-limit rejections | `bank_http_rate_limited_total` | Period count of requests refused by shared rate limits |
| Degradation level | `bank_degradation_level` | Maximum across workers, shown as L0 normal, L1 fallback model, L2 template only, L3 baselines, L4 database unavailable |

## What remains in the web console

The evaluator-only `/console/dashboard` is intentionally retained. It reads versioned, published evaluation
summaries and compares systems on a frozen synthetic workload. Grafana instead reports live telemetry from the
running deployment. Combining the two sources would make an offline benchmark look like production behavior, so
they remain separate and visibly labeled:

| Surface | Measurement | Source | Retention |
|---|---|---|---|
| Grafana | Live operational telemetry | OpenTelemetry to Prometheus | 7 days in development, 15 days or 2 GB in production |
| Web administrative dashboard | Offline, simulated, or projected evaluation | `GET /v1/eval/summaries` | Published summary artifacts |

## Access and hardening

Development: `make up PROFILES=obs` and `make api-obs`, then `http://localhost:3000/` (anonymous viewer, loopback).

Production: `OBS=1` in the server env file runs the `obs` profile on every `deploy/prod.sh up` and release (continuous
deployment included). Grafana listens on server loopback for the SSH tunnel and, with `GRAFANA_ROUTE=on`, behind
Caddy at `/grafana/` ([ADR 0045](../adr/0045-expose-grafana-read-only-under-grafana.md)):

- Caddy keeps the `/grafana` prefix (Grafana serves the sub-path itself), removes every `__Host-` and `__Secure-`
  cookie (the bank's session and CSRF cookies) from requests to Grafana, answers 404 for `/grafana/metrics`, and
  adds no CSP of its own: Grafana sends its own policy, and the SPA's strict policy is untouched.
- Grafana: secure `SameSite=Strict` cookies, sign-up, organisation creation, viewer editing, basic auth, snapshots,
  public dashboards, Live, Gravatar, embedding, update checks, plugin downloads, and its own metrics endpoint off;
  sessions end after 1 hour idle or 12 hours.
- Anonymous viewing is off unless `GRAFANA_ANONYMOUS_VIEWER=true`; the admin login (Key Vault secret
  `grafana-admin-password`) always works.
- Grafana and Caddy share the internal `observability` network and nothing else joins it.

Do not expose port 3000 in the public firewall and do not embed Grafana in the customer web application.

## Provisioning and change control

Dashboard JSON lives under `deploy/observability/grafana/provisioning/dashboards/`. Grafana loads every JSON file in
that directory as read-only, so durable changes are reviewed in Git rather than edited in the UI. The Prometheus
datasource has stable UID `prometheus` in both development and production.

`test_observability_config.py` parses every provisioned dashboard, including panels inside rows and the template
variables, and fails if a query names a metric that is neither in the telemetry catalog nor in its explicit list of
instrumentation and host metrics, if a dashboard is editable, uses another datasource, or mentions Jaeger, or if a
category panel cannot draw one value per series. JSON parsing, Compose rendering, and a live Grafana provisioning
check are the appropriate verification steps after a dashboard change. On 2026-10-05 every query of the three
dashboards was run against Prometheus 3.15.0 fed by the 0.161.0 collector (the production versions) with traffic from
the real telemetry adapters, and each returned data.

## Limitations

- Prometheus retention bounds the available history. The dashboard is not a warehouse or an audit ledger.
- Counter increases can be approximate at range boundaries and can briefly show fractional values after Prometheus
  extrapolation, even though the underlying events are discrete.
- A resolved turn does not prove policy-compliant automation. Use the published evaluation dashboard for safe
  automated resolution, containment, confidence intervals, and population slices.
- Cost is an estimate from the price table, deliberately high for unverified or unknown prices, and not a financial
  ledger.
- The degradation gauges refresh when a worker serves a turn or `/health/details`, so with no traffic the timeline
  keeps the last value.
- Host panels describe the whole VM; per-container CPU and memory are not collected (that needs the Docker socket).
- The dashboards show live traffic only. The smoke test after every deploy creates turns, so production panels
  include that synthetic traffic.
- Metrics have bounded technical labels only. Investigate a specific conversation through its execution record and
  trace ID, not through Grafana.
