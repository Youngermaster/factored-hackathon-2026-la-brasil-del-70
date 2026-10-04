# Security documents

The controls follow OWASP ASVS level 2 practices (CLAUDE.md section 7). How to report a vulnerability is in [SECURITY.md](../../SECURITY.md).

## Index

| Document | What it covers |
|---|---|
| [threat-model.md](threat-model.md) | STRIDE per component across the deployed topology, abuse cases, mitigations linked to code and tests, residual risks |
| [identity-and-sessions.md](identity-and-sessions.md) | The mock identity service, one-time codes, server-side sessions, step-up before a write, expiry, logout |
| [data-isolation.md](data-isolation.md) | Tool-layer scoping, row-level security, database roles and contexts, the append-only guards, and the tests that prove them |
| [prompt-injection.md](prompt-injection.md) | The defense layers, what the model can and cannot influence, and the known gaps |
| [data-use.md](data-use.md) | Which fields reach which model provider and why, redaction, provider retention |
| [data-retention.md](data-retention.md) | What is kept and for how long, the purge job, and what a regulated deployment would change |
| [demo-mode.md](demo-mode.md) | Why the public demo shows one-time codes, what that exposes, and how it is contained |
| [../data/data-use.md](../data/data-use.md) | The organizer data-use check for the committed sample before the repository goes public |
| [ADR 0008](../adr/0008-server-side-opaque-sessions.md), [0009](../adr/0009-row-level-security-as-defense-in-depth.md), [0010](../adr/0010-idempotency-keys-and-read-back-verification.md), [0031](../adr/0031-cookie-sessions-with-signed-double-submit-csrf.md) | The decisions behind sessions, row-level security, verified writes, and CSRF |

## The controls on one page

| Area | Control | Where it is enforced and proven |
|---|---|---|
| Identity | A trusted test session: a persona or a document number plus the last four phone digits only opens a challenge; one-time codes hashed at rest, 5-minute expiry, 5 attempts, constant-time comparison | `adapters/identity/`, `application/identity/sessions.py`, [identity-and-sessions.md](identity-and-sessions.md) |
| Sessions | Server-side opaque ids stored hashed, idle and absolute expiry, rotation on privilege change; step-up before every write | `adapters/persistence/{memory,postgres}/sessions.py`, the session contract suite, API tests |
| Cookies and CSRF | `__Host-` cookies, `HttpOnly`, `Secure`, `SameSite=Strict`; a signed double-submit token on every state-changing request | `api/dependencies.py`, the deployed smoke test |
| Authorization | Roles for customer, agent, evaluator on every route; another customer's resource answers 404, never 403 | `endpoint(...)` in `api/`, cross-customer API tests |
| Customer isolation | Tools never accept customer identifiers (the session injects them); forced row-level security with the context set inside each transaction; the application role owns nothing and has no `BYPASSRLS` | [data-isolation.md](data-isolation.md), `tests/integration/test_row_level_security.py` |
| Writes | Idempotency keys, a per-state tool allowlist, the action matrix, confirmation, step-up, and a read-back before success is reported | [ADR 0010](../adr/0010-idempotency-keys-and-read-back-verification.md), the write tool contract suites |
| Prompt injection | Records and user text are data inside delimiters, never tool selectors; heuristic detection raises the session's risk tier; model output is never executed | [prompt-injection.md](prompt-injection.md), the red-team scenarios |
| Model data | Prompt inputs are allowlists; identifiers, the credit profile, and the risk estimate never reach a model; a redaction decorator scrubs the rest | [data-use.md](data-use.md), `adapters/llm/redaction.py` |
| Input and output | Pydantic request models with explicit maximum lengths and no unknown keys; response models are allowlists; RFC 9457 problems without internals | `api/schemas/base.py`, the OpenAPI contract test |
| HTTP | CORS allowlist; CSP, HSTS in production, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, `frame-ancestors 'none'`; rate limits per IP and per session, shared across workers in production | `api/`, `deploy/caddy/Caddyfile`, `make csp-check` |
| Audit | Execution records and audit events are append-only at the database level; no hidden chain-of-thought is stored | `tests/integration/test_schema_guards.py`, [execution records](../workflows/execution-records.md) |
| Logging and retention | Structured JSON logs with a redaction processor; retention periods and a purge job | `bootstrap/logging.py`, [data-retention.md](data-retention.md) |
| Secrets | Environment only through pydantic-settings; production refuses default or empty secrets; gitleaks in pre-commit and over the full history | `bootstrap/settings.py`, `make check`, `make security` |
| Supply chain and containers | Lockfiles; pip-audit, `pnpm audit --prod --audit-level high`, bandit, hadolint, shellcheck, trivy, SBOMs; non-root, read-only, capability-dropped containers pinned by digest | `make security`, `make scan-images`, `tests/unit/test_deploy_config.py` |

Residual risks are in the [threat model](threat-model.md#residual-risks) and [LIMITATIONS.md](../../LIMITATIONS.md#remaining-risks).
