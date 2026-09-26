# Architecture overview

This page shows the monorepo components and the direction of their dependencies as of phase 01. Phase 17 replaces it with the final context, container, and component views.

## Components and dependency direction

An arrow from A to B means "A depends on B" (imports it, calls it, or reads from it).

```mermaid
flowchart TD
    subgraph web["apps/web (browser)"]
        wpages["pages"] --> wfeatures["features"]
        wfeatures --> wentities["entities"]
        wentities --> wshared["shared"]
        wfeatures --> wshared
    end

    subgraph api["services/api: bank_agent"]
        entry["asgi.py, cli.py<br/>entry points"]
        http["api"]
        boot["bootstrap"]
        adapters["adapters"]
        application["application"]
        policy["policy"]
        ports["ports"]
        domain["domain"]
        entry --> http
        entry --> boot
        http --> adapters
        boot --> adapters
        adapters --> application
        application --> policy
        policy --> ports
        ports --> domain
    end

    subgraph offline["Offline packages"]
        data["data_platform: bank_data"]
        ml["ml: bank_ml"]
        evals["evals: bank_evals"]
    end

    postgres[("PostgreSQL 16<br/>row-level security")]
    warehouse[("DuckDB warehouse<br/>data/")]
    registry[("Model registry<br/>filesystem or MLflow")]
    obs["OpenTelemetry collector<br/>Jaeger, Prometheus, Grafana"]

    wshared -- "HTTP, generated types" --> http
    adapters --> postgres
    adapters --> registry
    adapters -. "OTLP (phase 15)" .-> obs
    data --> warehouse
    data -- "seed demo subset" --> postgres
    ml --> warehouse
    ml --> registry
    evals -- "resolves systems from" --> boot
```

## Rules the diagram encodes

- **Backend layers** import inward only. `api` and `bootstrap` are independent of each other; the entry points wire them. import-linter enforces three contracts (layers, a pure core without framework or I/O imports, and no layer importing the entry points). See [ADR 0002](../adr/0002-uv-workspace-and-hexagonal-backend.md).
- **Frontend layers** import downward only, and features are reached only through their `index.ts`. ESLint boundary policies enforce this. See [ADR 0003](../adr/0003-frontend-layering-and-state.md).
- **The API never imports the offline packages.** It reads models through the `ModelRegistry` port and data through repositories. The evaluation harness depends on the API composition root, not the other way around.
- **The API connects to PostgreSQL as the application role**, which owns nothing and has no `BYPASSRLS`. See [deploy/README.md](../../deploy/README.md).

## Quality gates

`make check` runs every gate locally and CI runs the same gates in four jobs (python, web, guards, audit):

| Gate | Tool |
|---|---|
| Lint and format | ruff, ESLint, Prettier |
| Types | mypy (strict everywhere), TypeScript strict |
| Boundaries | import-linter, eslint-plugin-boundaries, each with a test proving the rules fire |
| Tests | pytest (unit with the network blocked, integration with PostgreSQL through testcontainers), Vitest with MSW |
| Coverage | Per-layer gates from `pyproject.toml`; 70% for web features |
| Security | bandit, gitleaks, pip-audit, pnpm audit |
| Docs | markdownlint, Mermaid parsing |
| Repository rules | No emojis, no AI attribution |
