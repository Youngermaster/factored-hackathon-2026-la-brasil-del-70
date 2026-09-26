# Architecture decision records

Each record captures one choice between real alternatives, in the [MADR](https://adr.github.io/madr/) format: context, options, decision, and consequences. Records are numbered in order and never rewritten; a later record supersedes an earlier one and both link to each other.

| Number | Title | Status | Date |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted | 2026-09-26 |
| [0002](0002-uv-workspace-and-hexagonal-backend.md) | Monorepo with a uv workspace and hexagonal backend layers | Accepted | 2026-09-26 |
| [0003](0003-frontend-layering-and-state.md) | Frontend layering and state rules | Accepted | 2026-09-26 |

## Adding a record

1. Copy the structure of an existing record into `NNNN-short-title.md` with the next number.
2. Describe the context and at least two real options with their trade-offs.
3. State the decision and its consequences, including what becomes harder.
4. Add a row to the table above in the same commit as the change it records.
