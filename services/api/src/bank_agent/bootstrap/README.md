# bank_agent.bootstrap

## Responsibility

Bootstrap turns the environment into a running process: typed settings, logging, and the composition root. It is the only package that reads environment variables and the only place that constructs concrete adapters.

| Module | Content |
|---|---|
| `settings.py` | `RuntimeSettings`, `DatabaseSettings`, `SecuritySettings` (secrets, CORS, `MAX_REQUEST_BODY_BYTES`, `RATE_LIMIT_*`), `LLMSettings` (including `LLM_API_BASE`), `ObservabilitySettings`, `LangfuseSettings`, `PolicySettings` (`POLICY_DIR`, `POLICY_DATA_AS_OF`), `RetrievalSettings` (`RETRIEVAL_*`), `WorkflowSettings`, `EvaluationSettings` (`EVAL_SUMMARIES_DIR`, `EVAL_SUMMARIES_PUBLIC`), `ConversationSettings` (`CONVERSATION_CREATION_LIMIT`, `CONVERSATION_CREATION_WINDOW_MINUTES`: the new-chat quota, with the public demo's higher default), and `load_settings()` with the production rules |
| `policy.py` | `build_policy()`: the policy pack, the synthetic credit catalog checked against it, the synthetic eligibility service, the tool parameters, and the data as-of date for policy windows, as `PolicyServices` |
| `retrieval.py` | `build_grounding()`: the bound clause lookup (every state resolved at startup), the grounding verifier, the retrieval index (built from the pack or loaded and checked), the retriever chosen by `RETRIEVAL_RETRIEVER` (the Qdrant ones behind the BM25 fallback), and informational retrieval with its thresholds, as `GroundingServices` |
| `embeddings.py` | `build_hosted_embedder()`: the hosted embedding gateway for Qdrant retrieval (redaction, cost accounting, circuit breaker, retry, LiteLLM with a timeout) |
| `logging.py` | `configure_logging()`: structlog JSON output for structlog and standard-library loggers, with `RedactionProcessor` |
| `container.py` | `Container`: builds the database engine, readiness checks, the prompt registry, the language model gateway, persistence, identity, policy, grounding, the workflow engines, and the HTTP use cases (`ConversationService`, `AgentInbox`, the evaluation summary reader); satisfies `ServiceProvider` structurally. Tests and the evaluation harness pass a clock, a telemetry double, `LlmOverrides` (an injected base client), and optionally `PersistenceServices` |
| `llm.py` | `build_llm_client()`: the provider chosen by `LLM_PROVIDER` wrapped in the decorator stack in the order `STACK_ORDER` documents (`docs/architecture/llm-gateway.md`) |

## Settings rules

- Variable names match the root `.env.example`; every new variable is documented there in the same commit.
- Secrets are `SecretStr`. In production (`APP_ENV=production`), `load_settings()` refuses `DEMO_MODE=true` and any session, CSRF, or database secret that is empty, shorter than 32 characters, a known default, or a `dev-only-` placeholder from `.env.example`. With `LLM_PROVIDER=litellm`, the primary key is also required; `LLM_TRACE_CONTENT=true`, cassette recording, a plain-http `LLM_API_BASE`, and a `*` or plain-http CORS origin are refused. Error messages name variables, never values.
- `SECRETS_DIR` names a directory of secret files named like their variables (the database, session, CSRF, model, and Langfuse keys); the production stack mounts them at `/run/secrets` from Azure Key Vault or the env file (ADR 0037, `deploy/secrets_stage.py`). An environment variable still wins over a file, so production with `SECRETS_DIR` refuses a secret variable in the environment, and a `SECRETS_DIR` that is not a directory stops startup.
- `POLICY_DIR` defaults to the repository `policies/` and `POLICY_DATA_AS_OF` to 2026-06-17, the organizer snapshot date; a malformed pack stops startup.
- `RETRIEVAL_INDEX_SOURCE` must be `stored` in production (a stored index must match the pack version); `dense` and `hybrid` need the optional `ml` extra, or an embedder injected into `Container` (tests and evaluations).
- Local Ollama models (`ollama/...`, `ollama_chat/...`) need no API key; every hosted model does (`KEYLESS_PROVIDERS` in `llm.py`).
- `LLM_PRICES_FILE` and `LLM_CASSETTE_DIR` default to `services/api/config/llm_prices.yaml` and `evals/cassettes/` (an empty value means the default). Outside tests, `LLM_PROVIDER=fake` without an injected client yields a client that refuses every call; the composition root never imports the test doubles.

## Redaction rules

- Masked keys (case-insensitive, any depth): `document_number`, `email`, `mobile_phone`, `landline_phone`, `address`, `password`, `otp`, `token`, `secret`, `authorization`, `cookie`, and any key containing one of those words or `api_key`.
- Scrubbed values in every string: emails, Brazilian CPF and CNPJ, Mexican CURP, dot-grouped numbers such as an Argentine DNI or a Colombian CC, phone numbers with separators, and runs of 7 or more digits. Integers of a million or more are masked too.

## Who may import it

Only the entry points `bank_agent.asgi` and `bank_agent.cli`, plus CLIs and the evaluation harness that resolve services from the container. Bootstrap imports `adapters` and everything below them, but never `api`.

## How to extend

- **Setting:** add a field to the class for its concern, document it in `.env.example`, and add a production rule in `production_problems()` if it is a secret.
- **Adapter wiring:** construct the adapter in `Container`, choosing the implementation from settings, and stack port decorators here.
- **Redaction:** add a key to `SENSITIVE_KEYS` or a pattern to `_VALUE_PATTERNS`, with a test case for it in `tests/unit/bootstrap/test_redaction.py`.

## How to test

Unit tests under `services/api/tests/unit/bootstrap/`. The shared fixture removes every settings variable and runs each test from an empty directory, so a developer's `.env` never affects a result. Coverage gate: 80% line coverage.
