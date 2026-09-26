# bank_agent.bootstrap

## Responsibility

Bootstrap turns the environment into a running process: typed settings, logging, and the composition root. It is the only package that reads environment variables and the only place that constructs concrete adapters.

| Module | Content |
|---|---|
| `settings.py` | `RuntimeSettings`, `DatabaseSettings`, `SecuritySettings`, `LLMSettings`, `ObservabilitySettings`, and `load_settings()` with the production rules |
| `logging.py` | `configure_logging()`: structlog JSON output for structlog and standard-library loggers, with `RedactionProcessor` |
| `container.py` | `Container`: builds the database engine, readiness checks, the prompt registry, and the language model gateway; satisfies `ServiceProvider` structurally. Tests and the evaluation harness pass a clock, a telemetry double, and `LlmOverrides` (an injected base client) |
| `llm.py` | `build_llm_client()`: the provider chosen by `LLM_PROVIDER` wrapped in the decorator stack in the order `STACK_ORDER` documents (`docs/architecture/llm-gateway.md`) |

## Settings rules

- Variable names match the root `.env.example`; every new variable is documented there in the same commit.
- Secrets are `SecretStr`. In production (`APP_ENV=production`), `load_settings()` refuses `DEMO_MODE=true` and any session, CSRF, or database secret that is empty, shorter than 32 characters, or a known default. With `LLM_PROVIDER=litellm`, the primary key is also required, and `LLM_TRACE_CONTENT=true` and cassette recording are refused. Error messages name variables, never values.
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
