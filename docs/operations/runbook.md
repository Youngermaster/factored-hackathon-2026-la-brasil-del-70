# Runbook

One section per Prometheus alert in `deploy/observability/alerts.yml` (the section anchors are the alert names, and a unit test keeps them in step). Each lists the symptom, how to diagnose it, and what to do. The degradation levels are explained in [degradation.md](degradation.md), the signals in [observability.md](observability.md).

First steps for any alert:

1. `curl -s localhost:8000/health/details` (development) or `curl -s https://<host>/health/details` (the deployed stack) shows the level, the reasons, and every component's state.
2. The Grafana dashboard "Bank agent: reliability and operations" (`localhost:3000`; on the VM through the SSH tunnel in [deploy/README.md](../../deploy/README.md), "Operate") shows the panel the alert queries.
3. A customer report comes with the `X-Request-ID` or `X-Trace-Id` of the failing response: search the JSON logs for the request id (`deploy/prod.sh logs api` on the VM), open the trace id in the Jaeger UI (`localhost:16686`, through the tunnel on the VM), and read the turn's execution record in the evaluator trace (`GET /v1/eval/conversations/{id}/trace`), which stores the same trace id.

The deployment operations (deploy, update, roll back, back up, restore, rotate secrets, the daily checks, and the take-down) are at the end of this page.

## LlmProviderDown

- **Symptom**: `bank_llm_circuit_state` is 2 (open) for a model for a minute; turns show `llm_fallback` and `/health/details` shows L1 (with a fallback) or L2.
- **Diagnose**: in Jaeger, `gen_ai.chat` spans with `error.type` (`llm_timeout`, `llm_rate_limited`, `llm_provider_error`); the panel "Model calls replaced by the deterministic path" names the prompts. Check the provider's status page and the key (never print it; `make env-check`). On the Azure VM, `deploy/prod.sh llm-probe` calls each configured deployment once per language from a throwaway container and prints `ok` or the error code per call (`not_configured`: the staged key file is empty, so the Key Vault value or the VM's per-secret grant is missing; `llm_provider_rejected`: wrong endpoint, deployment name, or API version; `llm_rate_limited`: the deployment's tokens-per-minute quota). For the local path, `ollama ps` and the model pull.
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

## Deployment operations

The single-host stack of [ADR 0019](../adr/0019-single-host-compose-deployment.md), operated with `deploy/prod.sh` from the checkout on the VM; the full guide, host setup included, is [deploy/README.md](../../deploy/README.md).

| Situation | Do |
|---|---|
| First deployment | `deploy/prod.sh init-env`, edit `deploy/.env.production`, `deploy/prod.sh check`, `build`, `up`, `seed`, `smoke` |
| New commit to deploy | On Azure the deploy workflow releases every CI-green push to `main` ([ADR 0038](../adr/0038-continuous-deployment-to-azure-with-github-actions.md)); the manual path is `deploy/prod.sh update` (pulls, backs up, builds, migrates, starts), then `deploy/prod.sh smoke` |
| The new release misbehaves | `deploy/prod.sh rollback`; if the update ran a migration the old code cannot use, `deploy/prod.sh restore <the backup update took>` first |
| Data lost or corrupted | `deploy/prod.sh restore deploy/backups/<file>.dump`; the API, the purge, and the edge stop during the restore and start again after it |
| A secret leaked or must change | the rotation table in the guide; `SESSION_SECRET` needs `deploy/prod.sh seed` afterwards |
| The certificate is close to expiry | Caddy renews by itself about 30 days before; if the uptime monitor warns, check `deploy/prod.sh logs web` for ACME errors (DNS, port 80) |
| Demo data changed by visitors | `deploy/prod.sh seed` restores blocked cards; a restore of an early backup resets everything |
| Switch the model, or roll it back | The section below |
| After 2026-10-16 | `deploy/prod.sh destroy --yes`, then release the cloud resources (the guide's last section) |

**Daily checks while the demo is up:** the external uptime monitor on `/health/live` (every 5 minutes, with certificate expiry), the daily smoke test from cron (`deploy/smoke_test.sh <PUBLIC_ORIGIN>`; exits non-zero on the first failure and never prints a secret), a glance at `/health/details` for the degradation level and the budget ratio, and the daily backup from cron. A smoke failure: `deploy/prod.sh status`, `deploy/prod.sh logs api`, then the alert section above that matches the symptom.

**Rate limits during a live session:** a room of judges behind one NAT shares one address and can hit the per-address limits (authentication 10 per minute). Raise `RATE_LIMIT_AUTH_PER_MINUTE` and `RATE_LIMIT_READ_PER_MINUTE` in the env file for the session, `deploy/prod.sh up`, and restore them afterwards; the per-session limits and the model budget still apply. Opening a chat can also answer `429 conversation-creation-limited`: the new-chat quota is per customer, so everyone on one persona shares it. The public demo defaults to 200 new chats per persona per hour when `CONVERSATION_CREATION_LIMIT` is empty; set it in the env file and `deploy/prod.sh up` if a session needs more ([demo mode](../security/demo-mode.md)).

### Switch or roll back the model

The model is a setting, not a release ([ADR 0044](../adr/0044-azure-openai-as-the-hosted-model-provider.md)); the Azure demo runs `azure/gpt-4.1-mini` with the fallback `azure/gpt-4o`.

1. **Prepare.** The deployment exists in the environment's Azure OpenAI account, its price entry is in `services/api/config/llm_prices.yaml` (an unknown model is charged at the highest known price times 1.5), and for a new key the Key Vault secret is set (`deploy/azure/keyvault-secrets.sh <vault> set LLM_API_KEY_PRIMARY`) with its per-secret grant for the VM identity.
2. **Edit** `deploy/.env.production` on the VM: `LLM_PRIMARY_MODEL`, `LLM_FALLBACK_MODEL`, and `LLM_API_BASE` when the account changes. Keep the old lines.
3. **Probe** with `deploy/prod.sh llm-probe`: every line must end in `ok`. The running API is untouched.
4. **Apply** with `deploy/prod.sh up` (about a minute of 502s while the API is recreated), then `deploy/prod.sh smoke` and `/health/details` (`llm_primary`, `llm_fallback`, `llm_budget` all `ok`). Within the next hour, a glance at the panel "Model calls replaced by the deterministic path" and at `budget_used_ratio`.
5. **Roll back** by restoring the old lines and running `deploy/prod.sh up`. To stop all model calls at once, `LLM_PROVIDER=fake` together with `LANGFUSE_ENABLED=false` (the API refuses Langfuse without a live model), then `deploy/prod.sh up`: every workflow answers on its deterministic path. A release rollback (`deploy/prod.sh rollback`, or the automatic one of continuous deployment) swaps images and never touches the env file, so it does not undo a model change; and a bad model setting makes the next release and its automatic restore fail together, which is why the probe comes first.
