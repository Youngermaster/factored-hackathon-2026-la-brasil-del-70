# bank_agent.api

## Responsibility

The HTTP layer: the FastAPI application factory, routers, request and response models, middleware, and the RFC 9457 problem-details mapping. It validates input, calls the application layer through services resolved from the provider, and encodes output. It contains no business rules.

## Modules

| Module | Content |
|---|---|
| `app.py` | `create_app(provider, config, problems=None)`: middleware (request id, security headers, CORS, body limit), the problem handlers, the routers, the OpenAPI document; closes the provider on shutdown |
| `provider.py` | `ServiceProvider` Protocol (clock, identity, conversations, agent inbox, evaluation summaries, credit product names, policy clauses, readiness) and `ApiConfig` |
| `config.py` | `SecurityConfig`: production flag, CSRF secret, CORS allowlist, body limit, rate limits per class, cookie names per environment |
| `dependencies.py` | Services, the session from the cookie, `role_dependency`, `require_csrf`, `rate_limit`, and `endpoint(...)`, which gives each route its dependencies and its `x-roles`, `x-rate-limit`, and `x-csrf` extensions |
| `cookies.py`, `csrf.py`, `ratelimit.py` | Cookie flags, signed double-submit tokens, the limiter per IP and per session over a `RateLimitStore` (in process by default, the shared PostgreSQL store when `ApiConfig.rate_limit_store` is set) |
| `middleware.py` | `RequestIdMiddleware`, `SecurityHeadersMiddleware`, `BodySizeLimitMiddleware` |
| `errors.py` | HTTP-layer errors (CSRF, not authenticated, role, payload, rate, service unavailable) |
| `problems.py`, `domain_problems.py` | `ProblemRegistry` (with `Retry-After` headers) and the mapping of HTTP-layer errors, identity refinements, and every domain error family to RFC 9457 problem types |
| `schemas/` | Request and response models: allowlists built from domain objects (`auth`, `conversations`, `trace`, `agent`, `evaluation`) |
| `routers/` | `health`, `auth` (`/v1/auth`), `conversations` (`/v1/conversations`), `agent` (`/v1/agent`), `evaluation` (`/v1/eval`) |
| `openapi.py` | The enriched OpenAPI document (security schemes, problem responses), `SchemaOnlyProvider` for the export, `render` |

The endpoint catalog, the auth model, and the error types are in [docs/api/README.md](../../../../../docs/api/README.md).

## Who may import it

Only the entry point `bank_agent.asgi`. `api` and `bootstrap` are independent layers, so the API never imports the container or settings; it receives them through `ServiceProvider` and `ApiConfig`.

## Rules

- Errors never leak internals: validation problems list locations and error types only, and unexpected exceptions become a generic 500 after being logged.
- Every request body model sets explicit maximum lengths and rejects unknown keys; response models are allowlists.
- Every state-changing route needs the CSRF token; every route declares its roles and rate class through `endpoint(...)`.
- Cross-customer resource access returns 404, not 403.

## How to extend

- **Endpoint:** add the route with `**endpoint(rate=..., roles=..., changes_state=..., operation_id=...)`, a session parameter from `role_dependency` for signed-in roles, and request and response models under `schemas/`; then run `make openapi` and add the row to `docs/api/README.md` (a test compares both with the code).
- **Error type:** add domain errors to a family in `bank_agent/domain/errors.py`, which `domain_problems.py` already maps; give an error its own entry in `DOMAIN_PROBLEMS` only when clients must act on it differently. Other typed errors use `ProblemRegistry.register(ErrorType, ProblemType(status, slug, title))`; subclasses map through their registered base.
- **Dependency:** add a property to `ServiceProvider` and implement it in `bootstrap/container.py`.

## How to test

Unit tests drive the app through the httpx ASGI transport with `FakeProvider` from `tests/bank_agent_test_support.py` (headers, limits, CORS, OpenAPI, credit data exposure). Integration tests in `tests/integration/api/` use the real container over the in-memory adapters and over PostgreSQL, with `ApiClient` from `tests/bank_agent_api.py`, which speaks the CSRF protocol. Coverage gate: 80% line coverage.
