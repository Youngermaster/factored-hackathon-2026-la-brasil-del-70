# 0044: Azure OpenAI as the hosted model provider

- Status: accepted
- Date: 2026-10-05
- Builds on: [ADR 0013](0013-litellm-behind-a-port-with-composable-decorators.md) (LiteLLM behind the `LLMClient` port, with composable decorators), [ADR 0037](0037-cloud-secret-management-with-azure-key-vault.md) (production secrets in Key Vault, read by the VM identity), [ADR 0038](0038-continuous-deployment-to-azure-with-github-actions.md) (continuous deployment to the Azure VM)

## Context

The language model only understands; deterministic code decides ([LLM gateway](../architecture/llm-gateway.md)). Every workflow has a deterministic path, so the system runs with no model at all (`LLM_PROVIDER=fake`), and that is how the public demo ran until 2026-10-05: the provider had never been chosen (pending actions 5, 7, and 45 in `docs/PROGRESS.md`). The repository's documentation had also named a Gemini model as the demo's primary model although no deployment used it.

The brief asks for an AI-first system that works securely with data, and for explicit trade-offs across autonomy, accuracy, latency, cost, and human oversight. A hosted model adds language understanding (escalation signals and slot extraction from free text in Spanish and Portuguese) on top of the deterministic engine, at the price of sending redacted, minimized text out of the VM. The production VM, its Key Vault, and its budget already live in one Azure subscription and resource group (`rg-bank-agent`).

## Decision drivers

- **Data use.** Prompts and completions must not train anyone's models, the processing region must be known, and only the redacted, minimized fields of `docs/security/data-use.md` may leave the VM.
- **Governance with what exists.** The key should live in the existing Key Vault with a per-secret read grant for the VM identity, and spend should appear on the same subscription as the rest of the deployment.
- **Structured outputs.** Every prompt the engine calls returns JSON validated against a Pydantic model, so the provider must support `json_schema` response formats through LiteLLM 1.102.1.
- **Cost and quota.** A turn makes one or two small calls (about 1,300 input and 40 output tokens each, measured below); the daily budget guard caps spend at `LLM_DAILY_BUDGET_USD`.
- **Latency.** A call should take about a second, so a turn stays interactive.
- **Velocity on the last day.** No code change on the request path: LiteLLM already speaks `azure/<deployment>`.

## Considered options

1. **Gemini through a Google AI Studio key** (`gemini/gemini-3.1-flash-lite`, listed at 0.25 and 1.50 USD per million input and output tokens, unverified). Cheap and supported by LiteLLM. The key and the billing would live in a Google account outside the Azure subscription and outside Key Vault's per-secret grants; the free tier lets Google use content to improve products, so only a paid key meets the data-use rules; `gemini-2.5-flash` is closed to new AI Studio users.
2. **The OpenAI API** (`openai/gpt-5-mini`, 0.25 and 2.00, unverified). Business API data is not used for training by default and structured outputs are first-class. Billing, quotas, and the key would sit in a separate OpenAI organization with its own controls, and processing happens wherever OpenAI runs it.
3. **Azure OpenAI in the team's own resource group** (`azure/gpt-4.1-mini` and `azure/gpt-4o`). Microsoft's data, privacy, and security page states that prompts and completions are not used to train generative AI foundation models without permission and are not available to OpenAI. The account sits in `rg-bank-agent` beside the VM, its keys go into the existing Key Vault, quotas and spend are visible in the same subscription, and `json_schema` output works with LiteLLM's default API version (verified by the probes below). The price per token of `gpt-4.1-mini` (0.40 and 1.60, GlobalStandard) is higher than options 1 and 2, and a GlobalStandard deployment may process a request in any Azure geography where the model is deployed.
4. **A self-hosted model with Ollama on the VM** (`ollama/qwen2.5:7b-instruct`, the `ollama` compose profile). Nothing leaves the VM and tokens cost nothing. It needs the 16 GB host row (the VM has 8 GB), runs on CPU (p50 4.1 s and p95 7.8 s per call on a developer machine in phase 11), and a 7B model is weaker at structured extraction than the hosted ones. It stays the local development option.
5. **Stay on `fake`.** Deterministic, free, nothing leaves the VM. Free-text paraphrases that the keyword router and the slot templates miss end in a clarifying question or a handoff, and the demo shows no language model at all.

## Decision

Option 3, with one Azure OpenAI account per environment:

- **Production**: account `aoai-la70-bank-agent` (Sweden Central) in `rg-bank-agent`. Primary deployment `gpt-4.1-mini` (model 2025-04-14, GlobalStandard, 60K tokens per minute); fallback deployment `gpt-4o` (model 2024-11-20, regional Standard, 50K tokens per minute) for degradation level L1. The keys are the Key Vault secrets `llm-api-key-primary` and `llm-api-key-fallback`, each readable by the VM identity alone through a per-secret `Key Vault Secrets User` grant. `LLM_API_BASE` is the account endpoint, shared by both deployments.
- **Evaluation**: account `aoai-la70-bank-eval` (East US, same resource group) with `gpt-4.1-mini` (GlobalStandard, 140K tokens per minute) and `text-embedding-3-small`, used only for offline evaluation and development, so evaluation runs never consume production quota or hold the production key. The subscription's `gpt-4.1-mini` GlobalStandard quota is 200K tokens per minute in total, split 60K and 140K.
- **Settings in production** (server env file): `LLM_PROVIDER=litellm`, `LLM_PRIMARY_MODEL=azure/gpt-4.1-mini`, `LLM_FALLBACK_MODEL=azure/gpt-4o`, `WORKFLOW_LLM_UNDERSTANDING=true`, `WORKFLOW_LLM_PHRASING=false`, `WORKFLOW_LLM_HANDOFF_SUMMARY=false`, `LLM_SESSION_TOKEN_LIMIT=200000`, `LLM_DAILY_BUDGET_USD=10`. Customer-facing wording stays template-based: the model reads, it does not write replies or handoff summaries.
- **Prices**: `services/api/config/llm_prices.yaml` lists the three deployments with the Azure Retail Prices API meters read on 2026-10-05. They stay `verified: false` until a person confirms them (pending action 7), so the budget guard charges 1.5 times the list price and errs high.

## Consequences

- Free-text understanding (escalation signals, slots) runs on a hosted model in Spanish and Portuguese, and every decision, action, and customer-facing sentence still comes from deterministic code and templates. If the model fails, times out, or the budget runs out, the gateway's fallback, circuit breakers, and degradation ladder return the deterministic paths, as before.
- **Shared endpoint.** The primary and the fallback share one account and one `LLM_API_BASE`. The fallback covers throttling and errors of one deployment (separate quotas), not an outage of the account or of Sweden Central. A second account in another region would be the next step for real redundancy.
- **Processing location.** `gpt-4.1-mini` is GlobalStandard: a request may be processed in any geography where Microsoft deploys the model, while data at rest, including the abuse-monitoring store, stays in the account's geography (Sweden). `gpt-4o` regional Standard processes in the account's geography. Only redacted, minimized fields are sent (`docs/security/data-use.md`, "Providers").
- **Cost.** At list price a call of 1,259 input and 39 output tokens (the measured mean below) costs about 0.00057 USD on `gpt-4.1-mini` and about 0.0043 USD on `gpt-4o` (projected from list prices, not billed amounts). The fallback costs about 7.5 times the primary per token, so a long primary outage spends the daily cap faster; the cap then switches the system to template-only mode until the next UTC day.
- **Evidence gap.** The committed evaluation cassettes were recorded with the local `ollama/qwen2.5:7b-instruct`; cassette keys include the model id, so no recorded evaluation describes `azure/gpt-4.1-mini`. Any quality claim for the Azure model needs a new recording on the evaluation account.
- **First call per worker.** LiteLLM is imported on the first model call of each API worker. In the local smoke run below the first call took 36 s (its first attempt hit the 20 s timeout and the retry succeeded); later calls took about a second. A backlog row covers importing it at startup.
- **API version.** With `LLM_API_VERSION` empty LiteLLM sends its default (`2025-02-01-preview` in 1.102.1). The setting pins another version without a code change; `2024-10-21` (GA) and `2025-04-01-preview` both returned valid structured replies, and an unsupported version was rejected by Azure, which shows the value reaches the service.

### Measured on 2026-10-05 (local development measurement, not an evaluation)

From a workstation in Colombia against the evaluation account (East US), `make llm-smoke` with `LLM_PRIMARY_MODEL=azure/gpt-4.1-mini` and no fallback: 32 of 32 fixture cases (four workflows, es and pt) returned valid structured replies; p50 1,169 ms, p95 2,137 ms, maximum 36,109 ms (the first call). The 32 calls used 40,292 input and 1,236 output tokens in total. `bank-agent llm-probe` returned valid replies in es and pt with the default API version, `2024-10-21`, and `2025-04-01-preview`. Production passed its smoke test in es and pt after the switch, and `/health/details` reported `llm_primary`, `llm_fallback`, and `llm_budget` as `ok`.

## Production delta

What production runs that the repository at `2ddabb0` did not describe, and what this record's change adds:

| Item | Before (repository at `2ddabb0`) | Production since 2026-10-05, about 15:30 UTC | Added by this change |
|---|---|---|---|
| Provider | `fake` default; docs named a Gemini model | `litellm` with `azure/gpt-4.1-mini`, fallback `azure/gpt-4o`, through env file edits only | Price entries for the three Azure deployments; docs and this record |
| Keys | Key Vault secrets defined, staged empty | `llm-api-key-primary` and `llm-api-key-fallback` set, per-secret VM grants | `deploy/prod.sh check` refuses an empty staged key file for a hosted model, naming the file |
| API version | not configurable | LiteLLM default | Optional `LLM_API_VERSION` (empty by default) through compose |
| Preflight | none | an operator script outside the repository | `bank-agent llm-probe` and `deploy/prod.sh llm-probe` |
| Langfuse | settings existed, never staged in production | off; keys stored in Key Vault with per-secret grants | Optional `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` staged, mounted, and checked; `LANGFUSE_ENABLED` and `LANGFUSE_BASE_URL` passed through compose, off by default |

## Changing the model

1. Create the deployment in the environment's account (or a new account), note its name, type, and tokens-per-minute quota, and add a price entry for `azure/<deployment>` to `services/api/config/llm_prices.yaml` with the retail meter in its note (`verified: false` until a person confirms it).
2. For a new account or key: store the key with `deploy/azure/keyvault-secrets.sh <vault> set LLM_API_KEY_PRIMARY` (or `_FALLBACK`) and make sure the VM identity has its per-secret read grant.
3. Edit `deploy/.env.production`: `LLM_PRIMARY_MODEL` (or `LLM_FALLBACK_MODEL`), and `LLM_API_BASE` when the account changes.
4. `deploy/prod.sh llm-probe`: every line must say `ok`. The running API is untouched until the next step.
5. `deploy/prod.sh up`, then `deploy/prod.sh smoke` and `/health/details` (`llm_primary`, `llm_fallback`, `llm_budget` all `ok`).
6. Rollback: restore the previous env file lines and run `deploy/prod.sh up`; to leave hosted models entirely, set `LLM_PROVIDER=fake` and `LANGFUSE_ENABLED=false` in the same edit. The release rollback of ADR 0038 swaps images, not the env file, so an env change is always reverted by hand.

The details are in `deploy/README.md` ("Choosing the model") and the [runbook](../operations/runbook.md) ("Switch or roll back the model").
