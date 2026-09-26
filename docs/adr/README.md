# Architecture decision records

Each record captures one choice between real alternatives, in the [MADR](https://adr.github.io/madr/) format: context, options, decision, and consequences. Records are numbered in order and never rewritten; a later record supersedes an earlier one and both link to each other.

Numbers 0008 to 0012 and 0014 to 0019 are reserved for the phases that already name them, so the table lists records by number, not by date.

| Number | Title | Status | Date |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted | 2026-09-26 |
| [0002](0002-uv-workspace-and-hexagonal-backend.md) | Monorepo with a uv workspace and hexagonal backend layers | Accepted | 2026-09-26 |
| [0003](0003-frontend-layering-and-state.md) | Frontend layering and state rules | Accepted | 2026-09-26 |
| [0004](0004-money-and-currency-handling.md) | Money and currency handling | Accepted | 2026-09-26 |
| [0005](0005-trust-state-append-only.md) | Trust state as append-only evidence with a monotonic risk tier | Accepted | 2026-09-26 |
| [0006](0006-handoff-and-execution-record-contracts.md) | Handoff and execution record contracts, with no chain-of-thought field | Accepted | 2026-09-26 |
| [0007](0007-dbt-duckdb-and-pandera-for-the-data-platform.md) | dbt-duckdb and Pandera for the data platform | Accepted | 2026-09-26 |
| [0013](0013-litellm-behind-a-port-with-composable-decorators.md) | LiteLLM behind a port with composable decorators | Accepted | 2026-09-26 |
| [0020](0020-four-workflows-and-the-workflow-registry.md) | Four workflows and the workflow registry | Accepted | 2026-09-26 |
| [0021](0021-credit-risk-and-eligibility-separation.md) | Separating conversation handling, risk estimates, and the synthetic eligibility service | Accepted | 2026-09-26 |
| [0022](0022-committed-bounded-data-sample.md) | A committed, bounded, pseudonymized organizer sample, and an explicit data source | Accepted | 2026-09-26 |

## Adding a record

1. Copy the structure of an existing record into `NNNN-short-title.md` with the next number.
2. Describe the context and at least two real options with their trade-offs.
3. State the decision and its consequences, including what becomes harder.
4. Add a row to the table above in the same commit as the change it records.
