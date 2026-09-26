# Contributing

Thank you for helping build the banking agent. This guide covers the mechanics; the full working agreement is [CLAUDE.md](CLAUDE.md), and it wins over this file when they differ.

## Set up

Install the prerequisites listed in the [README](README.md#prerequisites), then:

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
