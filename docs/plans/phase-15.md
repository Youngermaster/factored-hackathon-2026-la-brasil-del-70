# Phase 15 plan: reliability and observability

Not a plan-mode phase. The human delegated approvals to the orchestrator, so every open question below is decided by the session with its reasoning, and implementation follows this plan. The session runs in a git worktree while session 14b works on `main` (evals, a few engine fixes, `docs/PROGRESS.md`, `docs/BACKLOG.md`), so changes to `evals/` and the engine stay small and additive, and the progress entry is a new section.

Goal (brief, "a credible route to operation"): tracing, execution records linked to traces, monitoring, bounded retries, safe fallback, and tool-failure handling, each shown with evidence for the four workflows.

## Files to create or change

| Area | Files |
|---|---|
| Dependencies | `services/api/pyproject.toml`, `uv.lock`: OpenTelemetry API and SDK, the OTLP HTTP exporter, the FastAPI, SQLAlchemy, and httpx instrumentations |
| Telemetry port and adapter | `ports/telemetry.py` (a gauge instrument), `adapters/telemetry/opentelemetry.py` (spans and metrics through the OpenTelemetry API, the GenAI schema URL), the no-op adapter, the recording double, `bootstrap/observability.py` (providers, exporters, sampling, instrumentation) |
| Decorators | Tracing wrappers for the intent router, the policy evaluator, the risk estimator, and the eligibility service, stacked in the composition root; spans for tool calls in `GuardedToolset.run`; a span per turn and per state handler |
| Metrics from records | `application/engine/metrics.py`: turn latency, outcomes, escalations, dispatches and switches, tool calls and failures, eligibility outcomes, model fallbacks, and the unsafe-outcome detectors, read from the execution record after each turn |
| Degradation ladder | `domain/degradation.py` (levels, component states, status), `ports/reliability.py`, `application/reliability/ladder.py` (pure decision), `adapters/reliability/monitor.py` (circuit states, budget, model load results, database probe), `DegradationSettings` with one flag per fallback |
| Engine hooks | The model helpers skip calls in template-only mode; `decide.clarification_left` counts one extra attempt when degraded (stricter clarification); a limited-service prefix in L2; the trace id in the execution record |
| L3 | `bootstrap/models.py`: a registry failure or missing artifact serves the baselines (flag), a stricter router wrapper, the risk estimator falls back to `score_band@1` only when a setting allows it, otherwise an unavailable estimator (every eligibility goes to `review_required`); `bootstrap/policy.py`: a credit catalog that fails to load disables `credit` |
| L4 | `DatabaseUnavailableError`; the PostgreSQL unit of work and session store translate connection failures; 503 with `Retry-After`; web copy for the 503 in es, pt, and en |
| Tools | `GuardedToolset` enforces a per-call timeout (`TOOL_TIMEOUT_SECONDS`), recorded as a tool timeout |
| API | `X-Trace-Id` response header, trace id in JSON logs, readiness with dependency and degradation details, active session and rate-limit rejection metrics |
| Budget | A shared `BudgetLedger` with the in-memory and PostgreSQL adapters (migration `0011`), the daily spend ratio gauge, the 80 percent alert, template-only mode at 100 percent |
| Observability stack | `deploy/observability/`: collector on OTLP HTTP, Prometheus alert rules, Grafana dashboard provisioning and dashboard JSON; compose log rotation |
| Load test | `scripts/load/locustfile.py`, `make load-test`, results in `docs/operations/capacity.md` |
| Docs | `docs/operations/observability.md`, `degradation.md`, `runbook.md`, `capacity.md`; the LLM gateway, API, threat model, deploy, and package docs; an ADR; BACKLOG; PROGRESS |

## Tests to add

- Unit: the ladder decision table (every level, combinations, flags), the monitor over fake circuits and budgets, metric emission from execution records, the OpenTelemetry adapter against in-memory span and metric exporters (schema URL, sampling, attribute types, a broken exporter never raising), the log processor adding trace and span ids, redaction on real log output with a trace id, the settings, the tool timeout, the budget ledger contract.
- Integration: `X-Trace-Id` equals the trace id stored in the execution record; readiness reflects a database outage and a degraded level; the chaos suite; the PostgreSQL budget ledger under concurrent reservations.
- Chaos suite (`tests/integration/chaos/`): LLM timeouts and provider errors that open the circuit, then template-only turns; the daily budget exhausted mid-conversation; a database outage during a turn (503, `Retry-After`, nothing reported as done); a slow tool beyond its timeout; a partial write caught by the read-back; a model registry failure at startup; the risk estimator failing mid-conversation (`review_required`, never a default estimate); the credit catalog failing to load at startup (credit disabled, its intents out of scope, the other three unaffected). Each asserts a safe outcome, es and pt wording, a complete execution record, and no false success.

## Decisions on open questions (decided by the session under the delegated approval)

1. **Exporter protocol: OTLP over HTTP (protobuf) on port 4318**, not gRPC. The gRPC exporter pulls `grpcio` native wheels into the API image; the HTTP exporter needs only `requests` and `protobuf`, and the collector already listens on 4318.
2. **Metrics are pushed over OTLP to the collector, which exposes them to Prometheus** (the phase 01 layout), rather than a `/metrics` endpoint on the API: one pipeline for traces and metrics, no Prometheus client dependency, and no unauthenticated scrape endpoint on the API.
3. **Export is off unless `OTEL_ENABLED=true`.** Tests, CI, the evaluation harness, and a bare `uvicorn` run never try to export; the compose `obs` profile and `make api-obs` turn it on. Trace ids, the `X-Trace-Id` header, and log correlation work with export off, because the SDK tracer provider is installed either way.
4. **Sampling** is parent-based trace-id ratio (`OTEL_TRACES_SAMPLER_RATIO`, default 1.0). The trace id is stored in the execution record even when a trace is not sampled, so logs and records still correlate.
5. **GenAI semantic conventions stay pinned at 1.37.0** (phase 08); the adapter sets the schema URL `https://opentelemetry.io/schemas/1.37.0`. Closes the BACKLOG row.
6. **Metrics come from the execution record** after each turn rather than counters spread through handlers: metrics and records cannot disagree, and the engine stays nearly untouched while 14b edits it.
7. **A language model that is not configured (`LLM_PROVIDER=fake` without a client) is a configuration, not a degradation.** The LLM component reports `disabled` at L0; L2 starts only when configured providers fail or the budget runs out. Otherwise every default development run would show a limited-service notice.
8. **Levels combine by severity**: the reported level is the highest active one, and every active condition applies its own behavior (L2 and L3 can both be active). Writes never fail open at any level; L4 has no feature flag because failing closed is not optional.
9. **Unsafe-outcome detectors** reuse the grounding verifier's violation kinds: unverified or unsupported action claims (success without verification), approval wording, and internal figures (a risk estimate or credit profile value). A drafted phrasing with any of them is already rejected; a rendered template with any of them is now replaced by a safe handoff reply too, and each detection increments a counter.
10. **The budget ledger is shared through PostgreSQL** when a database is configured (`LLM_BUDGET_LEDGER=auto`), with the in-memory ledger for tests and the evaluation harness. PostgreSQL is already a dependency; Redis would add a service only for this. Shared rate limits stay phase 16 (they belong with the reverse proxy).
11. **Active sessions** are the sessions this process saw within the idle timeout, a per-process gauge summed by the dashboard; counting in the database would add a query per scrape.
12. **Load tool: Locust through `uv run --with locust`**, so nothing enters the lockfile or the image. k6 is not installed on this machine.
13. **Log retention**: compose rotates container logs (`json-file`, 10 MB times 5 files per service); Prometheus keeps 7 days; Jaeger keeps traces in memory only. Production retention is phase 16.

## Risks

- Instrumentation libraries may emit deprecation warnings, which pytest turns into errors. Mitigation: pin the stable HTTP semantic conventions and test the adapter in isolation.
- OpenTelemetry global providers are process-wide; tests must not leak them. Mitigation: the adapter owns its providers, and only the ASGI entry point installs globals.
- Merge conflicts with 14b in the engine and the progress files. Mitigation: additive edits, a separate progress section, metrics built from records.
- The load test measures one developer machine with the fake model; the numbers are labeled as a local measurement, not a production estimate.

## Out of scope

Cloud deployment and production retention (phase 16); shared rate limits (phase 16); Langfuse (the human decided against it).
