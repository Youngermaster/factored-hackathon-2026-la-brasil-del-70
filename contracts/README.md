# Contracts

## Responsibility

This directory holds the cross-boundary contracts: JSON Schemas for the documents that pass between the workflow engine, the persistence layer, the agent console, the glass box, and the evaluation harness. Phase 11 adds the OpenAPI snapshot next to them.

The Pydantic models are the single source of truth. `scripts/generate_contracts.py` generates the schemas; nobody edits a schema file by hand.

## Schemas

| File | Source model | Mode | Produced by | Consumed by |
|---|---|---|---|---|
| `schemas/handoff.v1.json` | `bank_agent.domain.handoff.Handoff` | serialization | workflow engine (phase 09) | agent inbox (phase 13), graders (phase 14) |
| `schemas/execution_record.v1.json` | `bank_agent.domain.execution_record.ExecutionRecord` | serialization | workflow engine (phase 09) | glass box (phase 13), graders and metrics (phase 14) |
| `schemas/decision.v1.json` | `bank_agent.domain.decision.Decision` | serialization | policy evaluator (phase 06) | execution records, glass box |
| `schemas/scenario.v1.json` | `bank_evals.scenarios.model.Scenario` | validation | scenario generators and reviewers (phase 14) | evaluation harness (phase 14) |
| `schemas/policy_clause.v1.json` | `bank_agent.domain.policy.ClauseMetadata` | validation | policy authors (phase 06) | policy loader (phase 06) |

- **Serialization mode** is used for documents the system produces. They match what `model_dump(mode="json")` emits: amounts are decimal strings (`"12.50"`), references are single strings (`transactions:T000123`, `DSP-CO-2.1@3`, `router:tfidf@3`), and every field is present, so every field is required.
- **Validation mode** is used for documents people and generators author. Fields with defaults may be omitted.
- Every schema is JSON Schema 2020-12 with `additionalProperties: false` at every level. Each file carries `$schema`, an `$id` of the form `https://bank-agent.local/contracts/schemas/<name>.v<major>.json`, and `x-schema-version`.
- Fields marked `x-pii` hold personal data and fields marked `x-internal` are never shown to customers or sent to a model.
- No output contract has a free-text reasoning field. A test fails if a property named like `reasoning`, `rationale`, `thought`, `chain_of_thought`, `cot`, `scratchpad`, or `inner_monologue` appears. See [ADR 0006](../docs/adr/0006-handoff-and-execution-record-contracts.md).

## Regenerating

```bash
make contracts                                                   # writes contracts/schemas/*.json
uv run --frozen python scripts/generate_contracts.py --check     # exit 1 and name stale files
```

`scripts/tests/unit/test_generate_contracts.py` runs in `make check` and CI and fails when a committed schema differs from its model. A Pydantic upgrade can change the rendering; regenerate and review the diff in the upgrade commit.

## Versioning

Each schema is versioned on its own with semantic versioning.

- **Major** (`v1` to `v2`): any change that can make a valid document invalid or change its meaning: removing or renaming a field, making a field required in an input contract, narrowing a type or a constraint, or changing the meaning of a value. The major version is part of the file name and the `$id`.
- **Minor** (`1.0.0` to `1.1.0`): additive changes only: a new optional field in an input contract, a new field in an output contract, or a new enum value.
- **Patch** (`1.0.0` to `1.0.1`): descriptions, titles, or constraint clarifications that accept exactly the same documents.

Documents carry `schema_version` (for example `1.0.0`); consumers accept any `1.x.y` for a `v1` schema.

Because every level rejects unknown keys, a document written under a newer minor version fails validation against an older one. All producers and consumers live in this repository and regenerate together; when that stops being true, consumers must upgrade before producers emit the new fields.

## Deprecation path

1. Mark the field deprecated in the model (`Field(deprecated=...)`), which adds `deprecated: true` to the schema, and add a row to the changelog below. Producers keep emitting it.
2. Keep it for at least one minor version, so every consumer can stop reading it.
3. Remove it only in the next major version. During the transition both files are generated side by side (for example `handoff.v1.json` and `handoff.v2.json`), and consumers state which majors they accept.

## Changelog

| Schema | Version | Date | Change |
|---|---|---|---|
| handoff | 1.0.0 | 2026-09-26 | Initial version |
| execution_record | 1.0.0 | 2026-09-26 | Initial version |
| decision | 1.0.0 | 2026-09-26 | Initial version |
| scenario | 1.0.0 | 2026-09-26 | Initial version, with the fields phase 14 lists |
| policy_clause | 1.0.0 | 2026-09-26 | Initial version |

## How to change a contract

1. Change the model, following the versioning rules above; bump the version in `scripts/generate_contracts.py` and, for a major version, add the new file alongside the old one.
2. Run `make contracts`.
3. Update the changelog and the consumers, and commit the model, the schemas, and the consumers together.
