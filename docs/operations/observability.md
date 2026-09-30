# Observability

Every request and every turn can be followed from the customer's screen to the database statement and back: the response carries `X-Request-ID` and `X-Trace-Id`, the JSON log lines carry the request id, the trace id, and the span id, the turn's execution record stores the same trace id, and the trace in Jaeger holds one span per HTTP request, turn, state handler, router dispatch, policy evaluation, tool call, risk estimate, eligibility assessment, model call, and SQL statement. Metrics go to Prometheus and a provisioned Grafana dashboard; alert rules map to the [runbook](runbook.md).

## Telemetry flow

```mermaid
flowchart LR
    subgraph api["API process"]
        http["FastAPI instrumentation<br/>server span, http.server.request.duration"]
        engine["Engine spans<br/>bank.turn, bank.workflow.state, bank.tool.call"]
        decorators["Tracing decorators<br/>router, policy, risk, eligibility, gen_ai.chat"]
        sql["SQLAlchemy spans"]
        metrics["TurnMetrics from the execution record<br/>DegradationMonitor gauges, HttpMetrics"]
        logs["structlog JSON with trace_id, span_id, request_id<br/>redaction processor"]
        record[("Execution record<br/>trace_id")]
    end
    collector["OpenTelemetry Collector<br/>OTLP HTTP 4318"]
    jaeger["Jaeger<br/>traces, 16686"]
    prom["Prometheus<br/>scrapes 8889, alert rules, 7 days"]
    grafana["Grafana<br/>dashboard, 3000"]
    http --> collector
    engine --> collector
    decorators --> collector
    sql --> collector
    metrics --> collector
    collector --> jaeger
    collector --> prom
    prom --> grafana
    jaeger --> grafana
    engine --> record
    logs --> stdout["Container log<br/>json-file, 5 x 10 MB"]
```

General OTLP export is on with `OTEL_ENABLED=true` (the compose `api` service passes the variable, `make api-obs` sets it). With both `OTEL_ENABLED=false` and `LANGFUSE_ENABLED=false`, nothing leaves the process, but trace ids, `X-Trace-Id`, and log correlation still work, because the SDK tracer provider is always installed (`bootstrap/observability.py`). Sampling is parent-based on the trace id ratio `OTEL_TRACES_SAMPLER_ARG` (1.0 keeps every trace); an unsampled turn still stores its trace id. Metrics are exported every `OTEL_METRIC_EXPORT_INTERVAL` milliseconds (15 s by default). Health probes are not traced.

## Optional Langfuse generation export

The runtime uses the already locked OpenTelemetry SDK and OTLP HTTP exporter 1.45.0 with LiteLLM 1.102.1. An existing Langfuse v4 server receives the spans; the API does not require the Langfuse Python SDK. The verifier uses Langfuse Python SDK 4.7 or later as a command-scoped dependency.

Set `LANGFUSE_ENABLED=true`, `LANGFUSE_BASE_URL`, `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY` in the API environment. The default base URL is `http://localhost:3000` for an existing local Langfuse instance; production requires HTTPS. `LLM_PROVIDER=litellm` and its optional extra are required. The flag defaults to false, and with it false the API creates no Langfuse exporter. `OTEL_ENABLED` may remain false: Langfuse has its own exporter on the existing tracer provider. For complete turn correlation, use `OTEL_TRACES_SAMPLER_ARG=1.0`.

The API sends one `gen_ai.chat` generation span per logical gateway call over OTLP/HTTP to `/api/public/otel/v1/traces`. The exporter reconstructs the span from a strict allowlist: OpenTelemetry trace and span IDs, turn correlation and conversation IDs, provider and model IDs, prompt ID and version, schema ID and content hash (the first 12 hash characters are its content-addressed version), success or error code, latency, token usage, and known USD cost. It discards prompt and completion content, retrieved records, tool data, customer IDs, exception messages, span events, links, and other attributes on both success and failure. The model receives the same inputs as before. No LiteLLM Langfuse callback is registered, so its default message capture is not used. A failed export logs its error class and batch size; the customer request still succeeds, and the log does not claim delivery. Shutdown flushes the OpenTelemetry batch processor. PostgreSQL remains the durable execution record.

For a local API process with an existing Langfuse service and a configured model, set the variables above, then run `uv run --frozen --package bank-agent --extra litellm uvicorn bank_agent.asgi:create_app --factory`. The live correlation verifier is opt in: `uv run --frozen --package bank-agent --extra litellm --with 'langfuse>=4.7,<5' python scripts/verify_e2e_tracing.py`. The verifier reads the same API settings, performs a real demo turn, and checks the PostgreSQL record against the Langfuse generation. It has not been rerun for this implementation pass.

If the general OTLP collector is also enabled, keep `OTEL_EXPORTER_OTLP_ENDPOINT` pointed at that collector rather than Langfuse to avoid duplicate generations. `LLM_TRACE_CONTENT=true` is refused when Langfuse is enabled. The collector can export content if that flag is enabled without Langfuse. The repo's `obs` profile uses Grafana on port 3000, so it conflicts with a Langfuse instance bound to the same host port; run one on another port when using both.

**Semantic conventions.** HTTP spans and metrics follow the stable HTTP conventions (`OTEL_SEMCONV_STABILITY_OPT_IN=http`). Model calls follow the OpenTelemetry GenAI semantic conventions **version 1.37.0**, pinned in `adapters/llm/tracing.py` (`GENAI_SEMCONV_VERSION`); the tracer and meter carry the schema URL `https://opentelemetry.io/schemas/1.37.0`. Project attributes use the `bank.` prefix.

**What never goes into telemetry.** Attribute values are ids, codes, versions, and counts: never message text, names, documents, amounts, the credit profile, or the risk estimate (the risk span names the model only). `LLM_TRACE_CONTENT=true` adds the already redacted prompt variables to `gen_ai.chat` spans and is refused in production. SQL spans carry the statement with bind placeholders, never the bound values.

## Signal catalog

The instrument catalog in `adapters/telemetry/catalog.py` is the source of truth (names, units, buckets, and the allowed attributes); a unit test fails when code emits something outside it or when an alert or dashboard queries a metric the service does not emit. Prometheus names replace dots with underscores, add `_seconds` for seconds, and `_total` for counters.

| Metric (OpenTelemetry name) | Kind | Attributes | Source |
|---|---|---|---|
| `http.server.request.duration` | histogram, s | method, route, status | FastAPI instrumentation |
| `bank.turn.duration` | histogram, s | workflow, outcome | execution record |
| `bank.turn.outcomes` | counter | workflow, outcome, language | execution record |
| `bank.escalations` | counter | workflow, reason code | the handoff of the turn |
| `bank.router.dispatches`, `bank.router.switches` | counter | workflow (from, to) | execution record |
| `bank.tool.calls`, `bank.tool.failures`, `bank.tool.duration` | counter, counter, histogram | tool, status, error code | execution record |
| `bank.eligibility.outcomes` | counter | product, outcome | execution record (synthetic service) |
| `bank.risk_estimator.failures` | counter | workflow | execution record |
| `bank.safety.unsafe_blocked` | counter | detector (`success_without_verification`, `approval_wording`, `internal_credit_value`), workflow | grounding violations of the turn |
| `bank.safety.interventions` | counter | intervention code, workflow | execution record |
| `bank.llm.fallbacks` | counter | prompt, error code, workflow | execution record |
| `gen_ai.client.operation.duration`, `gen_ai.client.token.usage` | histogram | operation, provider, model, prompt, error or token type | `TracingDecorator` |
| `bank.llm.cost_usd` | histogram | response model, price basis, prompt | `CostAccountingDecorator` |
| `bank.llm.circuit.state` | gauge (0 closed, 1 half-open, 2 open) | model | `DegradationMonitor` |
| `bank.llm.budget.daily_used_ratio`, `bank.llm.budget.refusals` | gauge, counter | cap | budget guard and monitor |
| `bank.degradation.level`, `bank.degradation.component` | gauge | component | `DegradationMonitor` |
| `bank.database.unavailable` | counter | none | unit of work and probes |
| `bank.sessions.active` | gauge (per process) | none | `HttpMetrics` |
| `bank.http.rate_limited` | counter | rate class, key kind (`ip` or `session`) | `HttpMetrics` |

Spans: `bank.turn` (turn id, conversation id, channel, workflow, state, outcome), `bank.workflow.state` (workflow, state, kind, next state, outcome), `bank.router.dispatch` (language, intent, confidence, below threshold, model), `bank.policy.evaluate` (workflow, policy state, decision, decisive rules, pack version), `bank.tool.call` (tool, status, attempts, error), `bank.risk.estimate` (product type, model), `bank.eligibility.assess` (product, estimate present, outcome, review reasons), `gen_ai.chat` (GenAI attributes), and the SQLAlchemy and HTTP spans.

## Logs and retention

Logs are JSON lines on stdout with `timestamp`, `level`, `logger`, `event`, `request_id`, and, inside a span, `trace_id` and `span_id`. The redaction processor (`bootstrap/logging.py`) masks sensitive keys and scrubs emails, document numbers, phones, and long digit runs in every value, tracebacks included; `trace_id` and `span_id` pass unredacted only when they are hex ids of the right length (tests: `tests/unit/bootstrap/test_logging.py`, `test_observability.py`).

| Store | Retention (development) | Where configured |
|---|---|---|
| Container logs | 5 files of 10 MB per service, rotated | `x-hardening.logging` in `docker-compose.yml` |
| Prometheus | 7 days | `--storage.tsdb.retention.time` in `docker-compose.yml` |
| Jaeger | In memory until the container restarts | Jaeger all-in-one defaults |
| Execution records, audit events | Kept (append-only by design) | PostgreSQL; purge policy for sessions and challenges is phase 16 |

## How to read the trace of one conversation

1. Take the `X-Trace-Id` of a turn response (the browser's network panel), or the `trace_id` of the turn in the evaluator trace (`GET /v1/eval/conversations/{id}/trace`), or of a log line.
2. Open `http://localhost:16686/trace/<trace id>` (service `bank-agent-api`). To see all turns of a conversation, search by the tag `bank.conversation_id=<id>`.
3. Read it top-down: the HTTP span (route and status); `bank.turn` (the workflow, final state, and outcome); `bank.router.dispatch` (which intent, how confident); one `bank.workflow.state` per handler that ran, each with its next state; inside them `bank.policy.evaluate` (the decision and the rule ids that decided it), `bank.tool.call` (status and attempts) with its SQL children, and `gen_ai.chat` (prompt id and version, model, tokens, cost, or the error type). A failed or skipped model call appears in the record as `fallback` with its code (`llm_circuit_open`, `degraded_template_only`).
4. The execution record with the same trace id explains the turn in audit terms: the clauses cited, the verification of every write, the models and prompts, latency by stage, and the safety interventions (including `degradation_l2` when the turn ran degraded).

## Running it locally

```bash
make up PROFILES=obs            # collector, Jaeger (16686), Prometheus (9090), Grafana (3000)
make api-obs                    # the API on :8000 exporting to the collector
make load-test LOAD_USERS=10    # traffic from the four workflows (raise the rate limits first)
```

Verified in phase 15 on a local stack: traces with the full span tree and SQL spans in Jaeger, every catalog metric that the traffic exercised in Prometheus, the alert rules loaded (`/api/v1/rules`), and the dashboard provisioned and querying Prometheus through Grafana.

## Limitations

- Grafana runs with anonymous read access and Jaeger keeps traces in memory: development only (phase 16 adds authentication and persistent storage).
- Active sessions and the degradation level are per process; dashboards sum or take the maximum over processes.
- The SQLAlchemy instrumentation declares support below SQLAlchemy 2.1; it is enabled past its version check after the spans were verified, and must be rechecked on upgrades.
