# Runbook

One section per Prometheus alert in `deploy/observability/alerts.yml` (the section anchors are the alert names, and a unit test keeps them in step). Each lists the symptom, how to diagnose it, and what to do. The degradation levels are explained in [degradation.md](degradation.md), the signals in [observability.md](observability.md).

First steps for any alert:

1. `curl -s localhost:8000/health/details` shows the level, the reasons, and every component's state.
2. The Grafana dashboard "Bank agent: reliability and operations" (`localhost:3000`) shows the panel the alert queries.
3. A customer report comes with the `X-Request-ID` or `X-Trace-Id` of the failing response: search the JSON logs for the request id, open the trace id in Jaeger (`localhost:16686`), and read the turn's execution record in the evaluator trace (`GET /v1/eval/conversations/{id}/trace`), which stores the same trace id.

## LlmProviderDown

- **Symptom**: `bank_llm_circuit_state` is 2 (open) for a model for a minute; turns show `llm_fallback` and `/health/details` shows L1 (with a fallback) or L2.
- **Diagnose**: in Jaeger, `gen_ai.chat` spans with `error.type` (`llm_timeout`, `llm_rate_limited`, `llm_provider_error`); the panel "Model calls replaced by the deterministic path" names the prompts. Check the provider's status page and the key (never print it; `make env-check`). For the local path, `ollama ps` and the model pull.
- **Act**: nothing is unsafe: every workflow answers on its deterministic path. If the outage is long, set `LLM_FALLBACK_MODEL` (L1) or accept L2. The circuit probes again after `LLM_CIRCUIT_RESET_SECONDS`; no restart is needed. Rate limiting (429) means lowering traffic or raising the provider quota.

## DegradedTemplateOnly

- **Symptom**: the level is 2 or 3 for two minutes. Customers see the limited-service notice (L2) or more clarifications and handoffs (L2, L3).
- **Diagnose**: the `reasons` in `/health/details`: `llm_unavailable` (see LlmProviderDown), `llm_budget_exhausted` (see LlmBudgetExhausted), `learned_models_unavailable` (the `model_fallback` warning at startup names the component and the error type), `credit_catalog_unavailable` (the `credit_catalog_unavailable` warning; the credit workflow is off).
- **Act**: for L3, restore the artifact (`make train` or copy `data/artifacts/models`) or the catalog files under `policies/credit/`, then restart. Never set `DEGRADATION_RISK_BAND_FALLBACK=true` to hide a missing learned estimator without the credit owner's approval: it changes the estimate the synthetic eligibility service sees.

## DatabaseUnavailable

- **Symptom**: level 4, or `bank_database_unavailable_total` increases. Every request that needs the database answers `503 dependency-unavailable` with `Retry-After`; `/health/ready` is 503, so an orchestrator stops routing to the instance.
- **Diagnose**: `docker compose ps postgres` (development) or the managed database's status; connections as the application role (`too many connections`, SQLSTATE 53300, is a pool or `max_connections` problem); a read-only server (a failover to a standby, `default_transaction_read_only`). SQLAlchemy spans in Jaeger show the failing statement and its duration.
- **Act**: restore the database or fail over to a writable primary. No manual cleanup is needed: a failed unit of work committed nothing, and a customer's retried turn (same `turn_id`) runs once. Writes whose outcome is unknown are never reported as done; a card block or case retried with the same idempotency key is not duplicated.

## LlmBudgetAt80Percent

- **Symptom**: `bank_llm_budget_daily_used_ratio` is at least 0.8; the log has `llm_budget_alert`.
- **Diagnose**: the panels "Tokens by model and prompt" and "Cost in USD by model and prompt": a prompt whose cost jumped (a longer context, repairs) or unusual traffic (look for one lineage or conversation near its own cap in `app.llm_budget`).
- **Act**: decide before 100 percent: raise `LLM_DAILY_BUDGET_USD` (a budget decision for the human), or let the service go template-only at 100 percent. Prices come from `services/api/config/llm_prices.yaml`; unverified entries are charged 1.5 times (pending action 7).

## LlmBudgetExhausted

- **Symptom**: the daily cap refused a call; the level is L2 with `llm_budget_exhausted` until the next UTC day.
- **Diagnose**: as for the 80 percent alert; `bank_llm_budget_refusals_total` by cap shows whether sessions or conversations also hit their own caps.
- **Act**: the service is safe in template-only mode. To restore model understanding the same day, raise the cap and restart, or wait for 00:00 UTC.

## UnsafeOutputBlocked

- **Symptom**: a runtime detector blocked a message: a success claim without a verified read-back, approval wording in a credit reply, or a risk estimate or credit profile value in customer text. The customer received `common.unsafe_blocked` and a person was offered.
- **Diagnose**: the record has `unsafe_output_blocked` in its safety interventions and the violation kinds in `grounding.violations`; `template_id` names the template that produced it. A template should never trigger a detector, so this is a defect in a template, a renderer parameter, or the verifier's lexicon.
- **Act**: treat as an incident. Reproduce with the turn's inputs, fix the template or the parameter, add a regression test, and review the golden texts. Do not relax the detector.

## InjectionSpike

- **Symptom**: more than 10 prompt-injection detections (`injection_detected` in customer text, `record_text_injection_flagged` in record text) in 10 minutes.
- **Diagnose**: the panel "Safety interventions by code"; the execution records with those interventions show the trust events added and the risk tier (raised tiers ask for step-up). Group by session lineage to see whether one actor is probing.
- **Act**: injected text is data and never selects a tool or changes a decision, so no action leaks. If one actor is probing, revoke its sessions (`SessionService.revoke`) and consider stricter rate limits for its address. Add new phrasings to the red-team set (phase 14).

## ErrorRateSpike

- **Symptom**: more than 5 percent of HTTP requests answer 5xx for five minutes.
- **Diagnose**: the panel "Requests by status" and the route panel; 503s come with a cause (the database, identity not configured); 500s are logged as `unhandled_exception` with the request id and the exception type (the message and traceback are redacted). Open the trace id of a failing request in Jaeger.
- **Act**: 503 from the database: see DatabaseUnavailable. 500: roll back the last deployment if it started with it, then fix with a regression test.

## TurnLatencyHigh

- **Symptom**: p95 turn latency above 5 seconds for ten minutes.
- **Diagnose**: the per-workflow latency panel and a slow trace in Jaeger: `gen_ai.chat` spans (a slow provider; the local 7B model takes about 3 to 6 seconds per call), `bank.tool.call` spans and their SQLAlchemy children (a slow database), or queueing in HTTP spans (CPU saturation; see [capacity.md](capacity.md)).
- **Act**: lower `LLM_TIMEOUT_SECONDS` or switch model; add database connections or API workers within the limits in capacity.md.

## EscalationSpike

- **Symptom**: more than 30 percent of turns end in a handoff for fifteen minutes.
- **Diagnose**: the panel "Escalations by workflow and reason": `tool_failure` points at a dependency, `clarification_exhausted` at understanding (often the model in L2), `human_requested` at customer demand.
- **Act**: fix the dependency; for understanding, check the level and the router's abstention rate. Staff the agent inbox for the backlog.
