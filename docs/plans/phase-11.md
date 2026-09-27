# Phase 11: API layer and HTTP security

Not a plan-mode phase: the human delegated approvals, so every open question is decided below with its reasoning. The pull at the start was a fast-forward no-op ("Already up to date"; a teammate branch `eda` was fetched, `main` did not move). The phase 09 walkthroughs (pending actions 21 and 25) are not blockers, on the human's instruction.

## What exists

- `api/`: the app factory, `ServiceProvider` and `ApiConfig`, request id middleware, the problem registry with the domain error families, and the health router. `api` and `bootstrap` may not import each other; `bank_agent.asgi` wires them.
- `application/identity/sessions.py`: login, step-up with rotation, resolution, logout, all audited. No routes.
- `WorkflowEngine.process_turn(TurnRequest) -> TurnResult`: creates a conversation on its first turn, pauses on an expired session, asks for step-up at write states, and resumes when the next turn arrives with a stepped-up session.
- Repositories for conversations, turns, execution records, handoffs (with the agent inbox lifecycle), and credit applications; RLS for customer, agent, and evaluator contexts.

## Files to create or change

| Area | Files |
|---|---|
| Settings | `bootstrap/settings.py`: `SecuritySettings` gains the rate limits, the body limit, the cookie mode, and `EVAL_SUMMARIES_PUBLIC`; new `EvaluationSettings` (`EVAL_SUMMARIES_DIR`); `LLMSettings.api_base`; production rules (no `*` origin, https origins, secure cookies) |
| Ports and adapters | `ports/evaluation.py` (`EvaluationSummaryReader`) and `adapters/evaluation/filesystem.py`; `HandoffQuery.workflows` in both handoff adapters; `CreditApplicationRepository.list_for_review` (agent, RLS-scoped) in both adapters; contract suites |
| Domain | `domain/evaluation.py` (`EvaluationSummary`, per workflow and aggregate, labeled offline); `TurnResult.workflow` |
| Application | `application/conversations/service.py` (create, turn, history, trace); `application/agent/inbox.py` (list, get, claim, resolve with audit events; credit application review reads); `SessionService.status` helpers if needed |
| Engine | `application/engine/gate.py`: a turn from a new session lineage (re-authentication) at a state with a `resume_state` goes back to that state and asks again, as after an expiry; `EngineData.lineage` |
| API | `api/config.py` (cookie and security config), `api/cookies.py`, `api/csrf.py`, `api/ratelimit.py`, `api/security_headers.py`, `api/body_limit.py`, `api/dependencies.py`, `api/roles.py`, `api/schemas/*` (DTOs), `api/routers/{auth,conversations,agent,evaluation}.py`, `api/openapi.py` (export, stable operation ids) |
| Composition | `bootstrap/container.py` exposes the new services; `bank_agent/asgi.py` builds `ApiConfig` from settings |
| Contract | `contracts/openapi.json`, `scripts/export_openapi.py`, `apps/web/src/shared/api/generated/schema.d.ts`, `apps/web/tooling/generate-api-types.mjs`, `make openapi` |
| Local LLM (human request) | `.env.example` comments, a zero-cost `ollama/qwen2.5:7b-instruct` price entry (`verified: true`, local), keyless local models in `bootstrap/llm.py`, `LLM_API_BASE`, `scripts/llm_smoke.py`, `make llm-smoke`, `make api-local-llm` |
| Docs | `docs/api/README.md`, `docs/security/threat-model.md`, ADR 0031, `docs/security/identity-and-sessions.md`, `docs/security/data-isolation.md`, `docs/architecture/llm-gateway.md`, package READMEs, `contracts/README.md`, BACKLOG, PROGRESS |

## Endpoint catalog (target)

| Method | Path | Role | CSRF | Rate class |
|---|---|---|---|---|
| GET | `/v1/auth/csrf` | anyone | no | auth |
| POST | `/v1/auth/start`, `/v1/auth/verify` | anyone | yes (anonymous token) | auth |
| POST | `/v1/auth/step-up/start`, `/v1/auth/step-up/verify` | any signed-in role | yes | auth |
| POST | `/v1/auth/logout` | any signed-in role | yes | auth |
| GET | `/v1/auth/me` | any signed-in role | no | read |
| POST | `/v1/conversations` | customer | yes | write |
| POST | `/v1/conversations/{id}/turns` | customer | yes | write |
| GET | `/v1/conversations/{id}` | customer | no | read |
| GET | `/v1/conversations/{id}/trace` | customer (own), evaluator (any) | no | read |
| GET | `/v1/agent/handoffs`, `/v1/agent/handoffs/{id}` | agent | no | read |
| POST | `/v1/agent/handoffs/{id}/claim`, `/v1/agent/handoffs/{id}/resolve` | agent | yes | write |
| GET | `/v1/agent/credit-applications`, `/v1/agent/credit-applications/{id}` | agent | no | read |
| GET | `/v1/eval/summaries` | evaluator, or anyone when `EVAL_SUMMARIES_PUBLIC=true` | no | read |
| GET | `/health/live`, `/health/ready` | anyone | no | none |

## Tests to add

- Unit (memory container, `FakeLLM` or the unconfigured client, `FixedClock`): cookies per environment, CSRF token signing and rotation, the rate limiter window math, security headers per response class, body limit, CORS allowlist, problem shapes, DTO mapping (customer trace without risk values), OpenAPI staleness, the credit data exposure walk over every customer-role schema, operation ids unique and stable, role matrix per route.
- Integration (the real container over testcontainers PostgreSQL, through the httpx ASGI transport): auth flow (start, verify, me, wrong code, expiry, lockout, demo code only when enabled, identification without a code yields no session); step-up and logout; CSRF missing or mismatched on every state-changing route; RBAC (customer on agent routes 403, agent on conversations 403, evaluator trace); cross-customer 404 with identical bodies; 413 and 422 limits; 429 with `Retry-After`; each workflow's normal path end to end plus one out-of-scope request; the card block resumed after the step-up route; handoff claim and resolve with audit events; eval summaries public and private.
- Contract suites: the workflow filter on handoffs and `list_for_review` on both backends.
- Web: a Vitest test that regenerates the TypeScript types from `contracts/openapi.json` and fails when the committed file differs.

## Decisions on open questions

1. **Cookies.** Production: `__Host-session` (`Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, no `Domain`) and `__Host-csrf` (the same without `HttpOnly`, so the SPA can read it). Development and test: `session` and `csrf` with `HttpOnly` and `SameSite=Strict` but without `Secure`, because the Vite server and uvicorn run over plain `http://localhost` and some browsers drop `Secure` cookies there; the `__Host-` prefix requires `Secure`, so it is production only. `Max-Age` of the session cookie is the time left to the absolute expiry, so the cookie never outlives the server session.
2. **CSRF: signed double-submit.** The token is `nonce.signature`, where the signature is HMAC-SHA256 over the binding and the nonce with `CSRF_SECRET`. The binding is the SHA-256 of the session token, or `anonymous` before login. A state-changing request (every POST) needs the `X-CSRF-Token` header equal to the cookie (constant-time) and a signature valid for its current session. A plain double-submit would accept any token an attacker can plant in a cookie; signing it to the session closes that. Login and step-up return a new token bound to the new session (rotation); logout returns an anonymous one. Without `CSRF_SECRET` (development only; production already refuses to start) the process uses a random secret, so tokens die with the process. A missing or wrong token is `403 csrf-token-invalid`.
3. **Expired sessions never reach the engine.** A cookie that resolves to an expired or revoked session is `401` on every route, including turns. Passing it to the engine would let a stale or stolen token append text to a customer's conversation. The engine's re-ask-after-expiry behavior is kept another way: a turn from a new session lineage (a new login) at a state with a `resume_state` (the write states) goes back to that state and asks again, exactly as after a pause. A step-up keeps the lineage, so a stepped-up turn still executes directly. This resolves the BACKLOG row about resuming after the step-up and re-authentication routes; the client sends the next message after the route succeeds.
4. **Rate limits: in-process sliding windows, no new dependency.** slowapi depends on `limits` and wraps routes with decorators that fight FastAPI dependencies; the limiter here is about 80 lines, keyed by rate class and by client IP and by session digest, and testable with an injected monotonic clock. Defaults per minute: `auth` 10 per IP and 10 per session, `write` 30 per IP and 20 per session, `read` 120 per IP and 60 per session; health is exempt. All are settings (`RATE_LIMIT_*`). A refusal is `429 rate-limited` with `Retry-After`. The client IP is the ASGI client; phase 16 runs uvicorn with `--proxy-headers` behind Caddy. Counters are per process (BACKLOG, phase 16).
5. **Body limit.** 16 KiB (`MAX_REQUEST_BODY_BYTES`) by `Content-Length` and by counting streamed bytes: a 2,000-character message is at most 8,000 bytes of UTF-8. Larger bodies are `413 payload-too-large`; field limits are `422`.
6. **CORS** uses Starlette's middleware with the allowlist from `CORS_ALLOWED_ORIGINS`, credentials allowed, methods GET and POST, headers `Content-Type`, `X-CSRF-Token`, and `X-Request-ID`. Production refuses `*` and non-https origins. The production SPA is same-origin behind Caddy, so CORS matters in development only.
7. **Headers.** Every response: `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, a `Permissions-Policy` that disables camera, microphone, geolocation, payment, USB, and similar features, `X-Frame-Options: DENY`, `Cross-Origin-Opener-Policy` and `Cross-Origin-Resource-Policy: same-origin`, and `Cache-Control: no-store` on `/v1`. HSTS (two years, `includeSubDomains`) in production only. The development `/docs` page gets a CSP that allows the Swagger UI assets; docs are off in production.
8. **Problem types.** New: `csrf-token-invalid` (403), `rate-limited` (429), `payload-too-large` (413), `identity-locked` (429 with `Retry-After`, as `domain_problems.py` planned), `verification-failed` (401, wrong code or unknown identification, one message), `code-expired` (401). The existing families stay; stack traces never leave the process.
9. **Roles.** One route table declares the roles of each operation; a dependency enforces them and the OpenAPI operation carries `x-roles`, which the docs catalog and the credit exposure test read. Agents get `403` on conversation history and trace (they see handoffs, never raw conversations); evaluators read every trace but no history (RLS gives them no turns).
10. **Conversations.** `POST /v1/conversations` opens an empty conversation at the router's START through a new `WorkflowEngine.open_conversation`, reusing the engine's own constructor. A turn body is `{text, client_turn_id?}`; a repeated `client_turn_id` replays the stored result, and one that belongs to another conversation is a `409`.
11. **DTOs are allowlists.** Response models are separate Pydantic classes built from domain objects by attribute, and unknown attributes are ignored, so a field added to the domain later never reaches a client by default. Customer and staff trace views are separate classes: the customer view shows that an estimate was used and its model, never the probability, interval, band, or flags, and drops the session id, trust events, risk tier, and safety interventions.
12. **Audit.** Login, step-up, and logout are audited by `SessionService` (unchanged); conversation actions by the tools (every call, redacted); the inbox service audits `handoff_claimed` and `handoff_resolved`; the conversation service audits `conversation_created`.
13. **Evaluation summaries.** A domain model (`EvaluationSummary`: system, run id, generated at, git sha, dataset version, per-workflow metrics and the aggregate, always labeled offline) behind a port, read from `EVAL_SUMMARIES_DIR` (default `evals/reports/summaries`). Phase 14 writes the files; until then the endpoint returns an empty list, which is the truth.
14. **Agent credit applications.** Read-only list and get under the current RLS (an agent reads an application only when a handoff references it). Widening that to every submitted intake is the existing phase 13 BACKLOG row.
15. **OpenAPI.** Explicit operation ids (`auth_start`, `conversations_send_turn`, ...), exported sorted and indented to `contracts/openapi.json` by `scripts/export_openapi.py` from an app built with a schema-only provider. The TypeScript types come from openapi-typescript 7.13.0 (MIT), pinned as a web devDependency and run through `apps/web/tooling/generate-api-types.mjs`, so `make openapi` and the Vitest staleness check use one function.
16. **Backlog row `list_my_credit_applications`** (owned by 11) moves to phase 13: it needs a `ToolName` value and a minor bump of every contract, which this phase avoids while it publishes the first OpenAPI snapshot.
17. **ADR number 0031**, as the human instructed (the prompt names 0017).
18. **Local LLM path (human request).** `LLM_API_BASE` (new, optional) passes `api_base` to LiteLLM. Models under the `ollama` and `ollama_chat` providers need no API key outside production; production still requires `LLM_API_KEY_PRIMARY` with `litellm`. The price table gets `ollama/qwen2.5:7b-instruct` at zero cost, `verified: true`, noted as local. `make llm-smoke` runs `scripts/llm_smoke.py` with `uv run --extra litellm`: every committed fixture cassette case (es and pt, four workflows, plus phrasing) goes through the configured gateway, structured outputs are validated against their output models, and a table of status and latency is printed. It checks reachability first and exits with a clear message when the provider is down. It is never part of `make check` or CI. `make api-local-llm` runs the API with the local provider.

## Risks

- Scope: this is the largest phase so far. Mitigation: vertical increments (security core, auth, conversations, agent and evaluation, OpenAPI, docs), each committed with its tests.
- Rate limits in tests: integration tests configure high limits except the rate-limit tests.
- The engine change runs under every workflow scenario; the full scenario suite must stay green.
- The OpenAPI rendering can change with a FastAPI upgrade; the staleness test catches it, and the upgrade commit regenerates.
