# Documentation index

Every document in the repository, grouped by purpose. Diagrams are Mermaid code blocks; `make docs-check` lints the Markdown and parses every diagram.

## Working agreement and status

| Document | Purpose |
|---|---|
| [CLAUDE.md](../CLAUDE.md) | Rules, stack, architecture, testing, documentation, and commit conventions for every session |
| [PROGRESS.md](PROGRESS.md) | Current state and the phase log: what was done, decisions, how to verify, limitations |
| [BACKLOG.md](BACKLOG.md) | Deferred items with the reason and the owning phase |
| [plans/](plans/) | The approved plan for each phase, and the team's kickoff notes |

## Organizer material

| Document | Purpose |
|---|---|
| [organizer/BRIEF.md](organizer/BRIEF.md) | Summary of the hackathon brief and evaluation criteria |
| [organizer/DATA_DICTIONARY.md](organizer/DATA_DICTIONARY.md) | Dataset schema |

## Architecture

| Document | Purpose |
|---|---|
| [architecture/overview.md](architecture/overview.md) | Monorepo components and their dependency direction |
| [architecture/domain-model.md](architecture/domain-model.md) | Domain class diagrams, case and credit application lifecycles, trust tiers, personal and internal data, error taxonomy |
| [architecture/ports-and-adapters.md](architecture/ports-and-adapters.md) | Ports, adapters present and planned, isolation rules, contract suites |
| [architecture/workflow-registry.md](architecture/workflow-registry.md) | The four workflows, the intents each owns, and what each answers, confirms, and escalates |
| [architecture/credit-separation.md](architecture/credit-separation.md) | Conversation handling, risk estimates, and the synthetic eligibility service kept apart |
| [../contracts/README.md](../contracts/README.md) | JSON Schema contracts and their versioning rules |
| [adr/README.md](adr/README.md) | Index of architecture decision records |
| [adr/0001](adr/0001-record-architecture-decisions.md) | Record architecture decisions |
| [adr/0002](adr/0002-uv-workspace-and-hexagonal-backend.md) | Monorepo with a uv workspace and hexagonal backend layers |
| [adr/0003](adr/0003-frontend-layering-and-state.md) | Frontend layering and state rules |
| [adr/0004](adr/0004-money-and-currency-handling.md) | Money and currency handling |
| [adr/0005](adr/0005-trust-state-append-only.md) | Trust state as append-only evidence with a monotonic risk tier |
| [adr/0006](adr/0006-handoff-and-execution-record-contracts.md) | Handoff and execution record contracts, with no chain-of-thought field |
| [adr/0020](adr/0020-four-workflows-and-the-workflow-registry.md) | Four workflows and the workflow registry |
| [adr/0021](adr/0021-credit-risk-and-eligibility-separation.md) | Separating conversation handling, risk estimates, and the synthetic eligibility service |

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
