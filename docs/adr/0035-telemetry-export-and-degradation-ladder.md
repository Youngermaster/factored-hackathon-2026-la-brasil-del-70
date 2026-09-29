# 0035: OpenTelemetry over OTLP HTTP, metrics from execution records, and a pure degradation ladder

- Status: accepted
- Date: 2026-09-29

Phase 15 decisions, taken by the session under the human's delegated approval; the plan is `docs/plans/phase-15.md`.

## Context

The brief asks for "a credible route to operation": tracing, execution records, monitoring, bounded retries, safe fallback, and tool-failure handling, shown with evidence. Phase 08 left a `Telemetry` port with a no-op adapter and GenAI attributes written through it; phase 01 left a compose `obs` profile (collector, Jaeger, Prometheus, Grafana) with nothing feeding it. Three questions had real alternatives: how telemetry leaves the process, where metrics come from, and how the service decides what to do when a dependency fails. The human ruled out Langfuse.

## Considered options

Export:

1. OTLP over gRPC to the collector: the SDK default, but it pulls `grpcio` native wheels into the API image.
2. A Prometheus `/metrics` endpoint on the API plus OTLP for traces: two pipelines, an unauthenticated scrape endpoint, and the Prometheus client as another dependency.
3. **OTLP over HTTP (protobuf) for traces and metrics to the collector**, which exposes metrics to Prometheus: one pipeline, about 5 MB of pure-Python packages, and the port the collector already opens.

Metrics:

1. Counters placed in handlers and tools where events happen: many edits in the engine, and numbers that can drift from the audit record.
2. **Metrics read from the execution record after it is stored**, plus the few signals only other layers know (circuit states, the budget, HTTP rejections, active sessions).

Degradation:

1. Each component handles its own failure (the phase 08 to 14 state): safe, but no single level, no notice to the customer, and no way to stop wasting calls on a dead provider.
2. **A pure ladder decision over dependency signals and one feature flag per fallback**, read once per turn by the engine and published by the health endpoint.

## Decision

- OTLP over HTTP to `OTEL_EXPORTER_OTLP_ENDPOINT` when `OTEL_ENABLED=true`. The SDK tracer provider is always installed, so trace ids, `X-Trace-Id`, log correlation, and the trace id in the execution record work with export off. Parent-based ratio sampling. The GenAI semantic conventions stay at 1.37.0 and the tracer and meter carry that schema URL.
- Turn metrics come from the execution record; the instrument catalog is the single list of names, units, buckets, and allowed attributes, checked by tests against the code, the alert rules, and the dashboard.
- The ladder: L0 normal, L1 fallback provider, L2 template-only (all providers unavailable or the daily budget spent), L3 baselines (learned models or the credit catalog failed to load), L4 database unavailable (fail closed, 503 with `Retry-After`). The highest active level is reported; every active condition applies its behavior; writes never fail open. A model that is not configured is a configuration (L0), not a degradation. A tampered artifact still stops startup.
- The model budget ledger moves to PostgreSQL (`app.llm_budget`) so API workers share one set of caps; the rate-limit counters stay per process until phase 16.

## Consequences

- Operators get one answer to "how degraded are we" (`/health/details`, the gauge, the alerts) and customers are told when the service is limited, in Spanish and Portuguese.
- Metrics cannot disagree with the audit trail, but a metric that the record does not carry needs a record field or a separate signal.
- The monitor is per process: each worker decides its own level from its own breakers. Sharing the level is phase 16 work if workers must agree.
- The SQLAlchemy instrumentation is enabled past its declared version range (checked by hand in Jaeger); upgrades must recheck it.
- Recovery from L3 needs a restart, because artifacts and the catalog load at startup.
