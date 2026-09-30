# Contributing

Thank you for helping build the banking agent. This guide covers the mechanics; the full working agreement is [CLAUDE.md](CLAUDE.md), and it wins over this file when they differ.

## Set up

Install the prerequisites listed in the [README](README.md#quickstart), then:

```bash
make setup     # uv sync, pnpm install, pre-commit hooks
make check     # every quality gate; must pass before any change is done
```

`make check` never needs `.env`. The integration tests start their own PostgreSQL container with generated credentials, so Docker must be running.

## Where code goes

Each package and app explains its responsibility, public interfaces, how to extend it, and how to test it in its README:

- [services/api](services/api/README.md) and its layer READMEs (domain, ports, policy, application, adapters, api, bootstrap, prompts);
- [apps/web](apps/web/README.md) and its layer READMEs (app, pages, features, entities, shared);
- [data_platform](data_platform/README.md), [ml](ml/README.md), [evals](evals/README.md), and [deploy](deploy/README.md).

Import boundaries are enforced: backend layers import inward only (import-linter), and web layers import downward only with features reached through their `index.ts` (ESLint). A boundary error means the code belongs in a different layer.

## Extending the system

Each guide names the files to touch and the tests to add. The step-by-step recipes are in [AGENTS.md](AGENTS.md) section 7; the package READMEs have the detail.

| Change | Guide |
|---|---|
| A persistence adapter (repository pattern, shared contract suites) | AGENTS.md "Add an adapter, a model, or a new port"; [adapters README](services/api/src/bank_agent/adapters/README.md); [ports and adapters](docs/architecture/ports-and-adapters.md) |
| A data source adapter | [data_platform README](data_platform/README.md#how-to-extend) |
| A model (router, resolver, or risk estimator: train, evaluate, register, promote, switch by settings) | [ml README](ml/README.md#how-to-add-a-model); never change a default without an end-to-end evaluation |
| A workflow, or disabling one | [application README](services/api/src/bank_agent/application/README.md#how-to-extend) and [workflow pages](docs/workflows/README.md#adding-or-disabling-a-workflow); `WORKFLOW_ENABLED` disables one without code changes |
| A workflow state | AGENTS.md "Add a workflow state" |
| A synthetic eligibility rule or a catalog product | AGENTS.md "Add or change a policy clause or rule" (credit clauses carry no approval wording); [policies README](policies/README.md); [eligibility](docs/policy/eligibility.md) |
| A policy clause or rule (parity across es, pt, en, lock, catalog) | AGENTS.md "Add or change a policy clause or rule" |
| A prompt or a prompt version (registry, cassettes, evaluation) | AGENTS.md "Add a prompt or a prompt version"; [prompts README](services/api/src/bank_agent/prompts/README.md) |
| A tool, an API route, a migration, a contract schema | The matching AGENTS.md recipes |
| A UI feature (layers, compound components, context, MSW tests) | AGENTS.md "Add a UI feature"; [features README](apps/web/src/features/README.md) |
| Evaluation scenarios | AGENTS.md "Add evaluation scenarios"; [evals README](evals/README.md) |

## Making a change

1. Write or update tests first where practical. Unit tests go in `tests/unit/` (no network, no database), integration tests in `tests/integration/`. Test names describe behavior, for example `test_rejects_dispute_after_window_closes`. Every bug fix adds a regression test.
2. Keep coverage gates green: 90% for domain, ports, policy, and application; 80% for adapters, api, bootstrap, and the other Python packages; 70% for web features.
3. Update the documentation that describes the code in the same commit. Diagrams are Mermaid code blocks; `make docs-check` validates them.
4. Record a choice between real alternatives as an ADR in [docs/adr](docs/adr/README.md).
5. Put anything out of scope in [docs/BACKLOG.md](docs/BACKLOG.md) with the reason and the owning phase.

Never disable, skip, or weaken a test, linter, type check, coverage gate, or security check to make a change pass. Fix the cause.

## Dependencies

Python dependencies are added with `uv add` (in the right package) and web dependencies with `pnpm add` in `apps/web`. Both lockfiles are committed. Check that a new dependency is maintained and permissively licensed, note the reason in the phase log, and ask the team before adding anything larger than about 50 MB installed or anything security-sensitive.

## Commits and pull requests

- Conventional Commits: `type(scope): summary`, imperative, at most 72 characters, no trailing period. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `build`, `ci`, `perf`, `security`. Scopes: `domain`, `policy`, `workflow`, `api`, `web`, `data`, `ml`, `evals`, `infra`, `docs`, `security`.
- The body explains why, not only what. One logical change per commit, with its tests and docs.
- No emojis anywhere and no AI attribution of any kind (no co-author trailers for tools, no "generated with" lines). Hooks and CI enforce both.
- Never bypass hooks with `--no-verify`, never force-push, and never rewrite published history.
- Pull requests follow the checklist in [.github/pull_request_template.md](.github/pull_request_template.md).
