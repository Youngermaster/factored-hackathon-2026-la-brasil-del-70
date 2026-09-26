# Documentation index

Every document in the repository, grouped by purpose. Diagrams are Mermaid code blocks; `make docs-check` lints the Markdown and parses every diagram.

## Working agreement and status

| Document | Purpose |
|---|---|
| [CLAUDE.md](../CLAUDE.md) | Rules, stack, architecture, testing, documentation, and commit conventions for every session |
| [PROGRESS.md](PROGRESS.md) | Current state and the phase log: what was done, decisions, how to verify, limitations |
| [BACKLOG.md](BACKLOG.md) | Deferred items with the reason and the owning phase |
| [plans/](plans/) | The approved plan for each phase |

## Organizer material

| Document | Purpose |
|---|---|
| [organizer/BRIEF.md](organizer/BRIEF.md) | Summary of the hackathon brief and evaluation criteria |
| [organizer/DATA_DICTIONARY.md](organizer/DATA_DICTIONARY.md) | Dataset schema |

## Architecture

| Document | Purpose |
|---|---|
| [architecture/overview.md](architecture/overview.md) | Monorepo components and their dependency direction |
| [adr/README.md](adr/README.md) | Index of architecture decision records |
| [adr/0001](adr/0001-record-architecture-decisions.md) | Record architecture decisions |
| [adr/0002](adr/0002-uv-workspace-and-hexagonal-backend.md) | Monorepo with a uv workspace and hexagonal backend layers |
| [adr/0003](adr/0003-frontend-layering-and-state.md) | Frontend layering and state rules |

## Packages and apps

| README | Scope |
|---|---|
| [services/api](../services/api/README.md) | API service and its layer READMEs |
| [apps/web](../apps/web/README.md) | Web application and its layer READMEs |
| [data_platform](../data_platform/README.md) | Data platform |
| [ml](../ml/README.md) | Learned components |
| [evals](../evals/README.md) | Evaluation harness |
| [deploy](../deploy/README.md) | Database roles and observability configuration |

## Contributing and security

| Document | Purpose |
|---|---|
| [CONTRIBUTING.md](../CONTRIBUTING.md) | How to set up, change, test, and commit |
| [SECURITY.md](../SECURITY.md) | Scope and how to report a vulnerability |

Later phases add `docs/workflows/`, `docs/data/`, `docs/evaluation/`, `docs/security/`, `docs/operations/`, `docs/frontend/`, and `docs/design/`, each listed here when it lands.
