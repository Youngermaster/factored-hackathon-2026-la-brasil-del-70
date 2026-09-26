# bank_agent.api

## Responsibility

The HTTP layer: the FastAPI application factory, routers, request and response models, middleware, and the RFC 9457 problem-details mapping. It validates input, calls the application layer through services resolved from the provider, and encodes output. It contains no business rules.

## Modules

| Module | Content |
|---|---|
| `app.py` | `create_app(provider, config, problems=None)`: builds the app, installs error handlers and middleware, closes the provider on shutdown |
| `provider.py` | `ServiceProvider` Protocol (what the API needs from the composition root) and `ApiConfig` |
| `middleware.py` | `RequestIdMiddleware`: validates or generates `X-Request-ID`, binds it to the log context, echoes it |
| `problems.py` | `ProblemRegistry` and the handlers for HTTP, validation, registered, and unexpected errors |
| `routers/health.py` | `GET /health/live` and `GET /health/ready` |

## Who may import it

Only the entry point `bank_agent.asgi`. `api` and `bootstrap` are independent layers, so the API never imports the container or settings; it receives them through `ServiceProvider` and `ApiConfig`.

## Rules

- Errors never leak internals: validation problems list locations and error types only, and unexpected exceptions become a generic 500 after being logged.
- Every request body model sets explicit maximum lengths (phase 11 adds the security middleware, CSRF, CORS, and rate limits).
- Cross-customer resource access returns 404, not 403.

## How to extend

- **Endpoint:** add a router module under `routers/`, include it in `app.py`, and add request and response models with explicit limits.
- **Error type:** call `ProblemRegistry.register(ErrorType, ProblemType(status, slug, title))` once; subclasses map through their registered base.
- **Dependency:** add a property to `ServiceProvider` and implement it in `bootstrap/container.py`.

## How to test

Unit tests drive the app through the httpx ASGI transport with `FakeProvider` from `tests/bank_agent_test_support.py`; integration tests use the real container and PostgreSQL. Coverage gate: 80% line coverage.
