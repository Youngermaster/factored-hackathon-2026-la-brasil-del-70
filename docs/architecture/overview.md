# Architecture overview

The final views of the system at three C4-like levels (context, containers, and the components of the API), drawn as flowcharts, plus the sequence of one customer turn. Details live in [domain-model.md](domain-model.md), [ports-and-adapters.md](ports-and-adapters.md), [workflow-registry.md](workflow-registry.md), [credit-separation.md](credit-separation.md), [llm-gateway.md](llm-gateway.md), and the [workflow pages](../workflows/README.md). An arrow from A to B means "A calls, reads, or depends on B".

## System context

```mermaid
flowchart LR
    customer["Customer<br/>Mexico, Colombia, Argentina<br/>chats in es or pt"]
    agent["Bank agent<br/>handoffs, credit reviews<br/>(console in en or es)"]
    evaluator["Evaluator<br/>execution records, results"]
    system["Banking customer-service system<br/>four workflows on one engine"]
    llm["Language model provider<br/>fake (default), local Ollama,<br/>or a hosted model through LiteLLM"]
    organizer[("Organizer data<br/>synthetic bank, 13 tables<br/>S3 delivery or committed sample")]
    customer -- "chat, one-time codes" --> system
    agent -- "inbox, claim, resolve" --> system
    evaluator -- "records, evaluation view" --> system
    system -- "redacted prompts, structured outputs" --> llm
    system -- "batch ingest under contracts" --> organizer
```

## Containers

```mermaid
flowchart TB
    browser["Browser"] --> web
    subgraph host["One host (Docker Compose; dev or the production stack)"]
        web["web<br/>Caddy: TLS, CSP, the static React SPA,<br/>reverse proxy for /v1 and /health"]
        api["api<br/>FastAPI on uvicorn (2 workers in production)"]
        jobs["jobs<br/>migrate, seed, retention purge (owner role)"]
        pg[("PostgreSQL 16<br/>forced row-level security,<br/>append-only records and audit")]
        obs["obs profile<br/>OpenTelemetry collector, Jaeger,<br/>Prometheus with alerts, Grafana"]
        qdrant[("rag profile: Qdrant<br/>vector index of the policy clauses,<br/>derived and rebuildable")]
    end
    subgraph offline["Offline, on a developer machine or CI"]
        dp["data platform (bank-data)<br/>Pandera contracts, DuckDB, dbt:<br/>bronze, silver, gold, reports"]
        mlp["ML (bank-ml)<br/>router, resolver, risk estimator;<br/>MLflow tracking"]
        ev["evaluation (bank-evals)<br/>B0, B1, P on held-out scenarios"]
        reg[("model registry<br/>digest-checked JSON artifacts")]
    end
    web --> api
    api --> pg
    jobs --> pg
    api -- "OTLP" --> obs
    api -- "LiteLLM: chat and query embeddings" --> llm["Model provider"]
    api -. "qdrant or qdrant_hybrid only;<br/>BM25 when unavailable" .-> qdrant
    dp -- "gold to seed" --> jobs
    mlp --> reg
    api -- "loads champion or baseline" --> reg
    ev -- "resolves systems from the composition root" --> api
```

The production topology, hardening, and the path to managed services are in [ADR 0019](../adr/0019-single-host-compose-deployment.md) and [deploy/README.md](../../deploy/README.md); telemetry and alerts in [observability](../operations/observability.md).

## Components of the API

```mermaid
flowchart TB
    subgraph edge["api (FastAPI)"]
        routers["routers: auth, conversations, preferences,<br/>agent, evaluation, health"]
        guards["endpoint(): roles, CSRF,<br/>rate class, problem details"]
    end
    subgraph boot["bootstrap"]
        settings["settings<br/>(only module reading the environment)"]
        container["container.py<br/>composition root"]
    end
    subgraph app["application"]
        engine["engine: turn loop, router dispatch,<br/>gate, templates, grounding verifier"]
        workflows["workflows: account_inquiry,<br/>card_support, dispute, credit"]
        tools["tools: per-state allowlist,<br/>idempotent writes, read-back"]
        other["identity, handoffs, agent inbox,<br/>reliability ladder"]
    end
    subgraph core["policy, ports, domain (pure)"]
        policy["policy kernel: pure rules by id,<br/>clause files, synthetic eligibility"]
        ports["ports: repositories, LLM, router,<br/>resolver, risk estimator, retriever, clock"]
        domain["domain: entities, Money,<br/>errors, contracts"]
    end
    subgraph adapters["adapters"]
        persistence["persistence: postgres, memory, duckdb"]
        llmstack["llm: LiteLLM or fake, wrapped in redaction,<br/>budget, retry, timeout, breaker, tracing"]
        models["models: keyword and learned routers,<br/>rule and LightGBM resolvers, risk estimators"]
        misc["retrieval (BM25; Qdrant with a BM25 fallback),<br/>vector store, embeddings, identity, telemetry, prompts"]
    end
    routers --> guards --> engine
    container --> settings
    container -- "builds" --> adapters
    routers -. "ServiceProvider" .-> container
    engine --> workflows --> tools
    workflows --> policy
    engine --> policy
    tools --> ports
    engine --> ports
    policy --> domain
    ports --> domain
    adapters -- "implement" --> ports
```

`api` and `bootstrap` never import each other; the entry points (`asgi.py`, `cli.py`) wire them. The evaluation harness and the CLIs resolve from the same composition root, so a provider, a model, or a store changes by settings only.

## One customer turn

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer
    participant W as Web app
    participant A as API
    participant E as Engine
    participant K as Policy kernel
    participant T as Tools
    participant DB as PostgreSQL
    participant G as LLM gateway
    C->>W: types a message
    W->>A: POST /v1/conversations/{id}/turns (cookie, CSRF token, turn id)
    A->>A: session, role, CSRF, rate limit, request limits
    A->>E: TurnRequest
    E->>DB: turn id already stored? (replay returns the stored result)
    E->>E: language, injection heuristics, escalation and privacy signals
    E->>K: evaluate START (refuse, escalate, or continue)
    E->>G: understand (redacted text, allowlisted inputs), when the model is enabled
    G-->>E: structured output, or an error (deterministic fallback)
    E->>E: router dispatch, then the state's handler
    E->>T: tool call from the state's allowlist (customer from the session)
    T->>DB: read, or idempotent write then read-back, inside an RLS transaction
    DB-->>T: rows for this customer only
    E->>K: evaluate the state's bound rules with the verified facts
    K-->>E: Decision (rule ids, clause versions)
    E->>E: template, grounding verifier, optional phrasing
    E->>DB: one unit of work: turn, conversation, handoff, execution record
    E-->>A: TurnResult
    A-->>W: message, parts, outcome
    W-->>C: reply, with the glass box reading the execution record
```

## Rules the diagrams encode

- **Backend layers** import inward only (`domain` <- `ports` <- `policy` <- `application` <- `adapters` <- `api` and `bootstrap`). import-linter enforces seven contracts, among them the layers, a pure core without framework or I/O imports, production code never importing the test doubles, and the evaluation harness separation. See [ADR 0002](../adr/0002-uv-workspace-and-hexagonal-backend.md).
- **Frontend layers** import downward only (`pages` -> `features` -> `entities` -> `shared`), and features are reached only through their `index.ts`; ESLint boundary rules enforce this ([ADR 0003](../adr/0003-frontend-layering-and-state.md)).
- **The language model understands; code decides.** The model returns structured outputs validated against Pydantic models; decisions come from the policy kernel, writes from allowlisted tools, and replies from templates that pass the grounding verifier. With `LLM_PROVIDER=fake` every workflow still works on its deterministic path.
- **The API never imports the offline packages.** It reads models through the `ModelRegistry` port and data through repositories.
- **The API connects to PostgreSQL as the application role**, which owns nothing and has no `BYPASSRLS` ([data isolation](../security/data-isolation.md)).

## Quality gates

`make check` runs every gate locally, and CI runs the same gates:

| Gate | Tool |
|---|---|
| Lint and format | ruff, ESLint, Prettier |
| Types | mypy (strict), TypeScript strict |
| Boundaries | import-linter, ESLint boundary rules, each with a test proving the rules fire |
| Tests | pytest (unit with the network blocked, integration with PostgreSQL through testcontainers, contract suites per port), Vitest with MSW and vitest-axe |
| Coverage | Per-directory gates from `pyproject.toml`; 70% for web features |
| Security | bandit and gitleaks in `make check`; pip-audit, pnpm audit, hadolint, shellcheck, trivy in `make security` and CI |
| Docs | markdownlint, Mermaid parsing |
| Repository rules | No emojis, no AI attribution, the committed sample's bound |
