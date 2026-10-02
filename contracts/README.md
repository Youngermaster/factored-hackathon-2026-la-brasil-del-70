# Contracts

## Responsibility

This directory holds the cross-boundary contracts: JSON Schemas for the documents that pass between the workflow engine, the persistence layer, the agent console, the glass box, and the evaluation harness, and `openapi.json`, the HTTP API contract.

The Pydantic models are the single source of truth. `scripts/generate_contracts.py` generates the schemas; nobody edits a schema file by hand.

## Schemas

| File | Source model | Mode | Produced by | Consumed by |
|---|---|---|---|---|
| `schemas/handoff.v1.json` | `bank_agent.domain.handoff.Handoff` | serialization | workflow engine (phase 09) | agent inbox (phase 13), graders (phase 14) |
| `schemas/execution_record.v1.json` | `bank_agent.domain.execution_record.ExecutionRecord` | serialization | workflow engine (phase 09) | glass box (phase 13), graders and metrics (phase 14) |
| `schemas/decision.v1.json` | `bank_agent.domain.decision.Decision` | serialization | policy evaluator (phase 06) | execution records, glass box |
| `schemas/scenario.v1.json` | `bank_evals.scenarios.model.Scenario` | validation | scenario generators and reviewers (phase 14) | evaluation harness (phase 14) |
| `schemas/policy_clause.v1.json` | `bank_agent.domain.policy.ClauseMetadata` | validation | policy authors (phase 06) | policy loader (phase 06) |

- **Serialization mode** is used for documents the system produces. They match what `model_dump(mode="json")` emits: amounts are decimal strings (`"12.50"`), references are single strings (`transactions:T000123`, `DSP-CO-2.1@3`, `router:tfidf@3`), and every field is present, so every field that existed in the major version's first release (`1.0.0`) is required. Fields added in a later minor version are the exception (see "Fields added in a minor version").
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

## Fields added in a minor version

Decision recorded in phase 02b (approved 2026-09-26). The problem: in a serialization-mode schema every field is required, including a new field with a default. A document stored under `1.0.0` lacks that key, so it would fail the `1.1.0` schema even though the model accepts it, and "consumers accept any `1.x.y`" would stop being true.

The rule:

1. Every field added to a contract within a major version carries the `AddedIn("<version>")` marker from `bank_agent.domain.base`, for example `workflow: Annotated[WorkflowRef | None, AddedIn("1.1.0")] = None`. The schema shows it as `"x-added-in": "1.1.0"`.
2. A hook on `DomainModel` leaves marked fields out of `required`, in every schema mode. Every field that existed in `x.0.0` stays required. Fields inside a model that is itself new are not marked: a document that has the parent field was written by a producer that emits all of its fields.
3. A version gate (`check_added_fields`) rejects a document whose `schema_version` predates a marked field while that field holds a non-default value, so a version label never understates what a document contains.
4. Removing a marker, or making a marked field required, is a major change.

A stored `1.0.0` document therefore validates against the `1.1.0` models and schemas unchanged. Re-serializing it through a `1.1.0` model emits the new keys at their defaults; the `1.1.0` schema accepts that document and the `1.0.0` schema does not, which is the existing "consumers upgrade first" rule.

Tests: golden `1.0.0` documents, frozen from the phase 02 builders, are validated against the models and the committed schemas (`services/api/tests/fixtures/contracts/v1.0.0/`, `evals/tests/fixtures/contracts/v1.0.0/`); a negative control shows that an unmarked new field breaks them; a schema walk checks that exactly the marked fields are optional. The alternative, keeping every field required and documenting that consumers read stored documents through the models, was rejected because it makes the schemas unusable for stored documents and for consumers outside Python.

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
| handoff | 1.1.0 | 2026-09-26 | Adds optional `workflow`, `credit_review` (with an internal risk part), and `card_request`, marked `x-added-in`; widens `request.intent`, `actions_taken.action`, `escalation_reason.code` (card and credit codes), the source reference tables, and the clause family pattern (`ACC`, `CRE`, `ELG`); new documents default to `1.1.0` |
| execution_record | 1.1.0 | 2026-09-26 | Adds optional `workflow_before`, `risk_estimates` (internal), and `eligibility_assessments`, kept as separate fields; widens intents, tool names, action kinds, model components (`risk_estimator`), and the clause family pattern; new documents default to `1.1.0` |
| decision | 1.1.0 | 2026-09-26 | Widens the clause family pattern (`ACC`, `CRE`, `ELG`) and `action` (`submit_credit_application`); new documents default to `1.1.0` |
| scenario | 1.1.0 | 2026-09-26 | Adds `workflow`, `expected_workflow_path`, and `expected_eligibility_outcome`; the fixtures `credit_profile_override`, `existing_credit_application`, and `model_unavailable`; the assertions `credit_application_exists`, `credit_application_count`, and `eligibility_outcome`; the disclosure kinds `balance`, `as_of_date`, `eligibility_reason`, `review_path`, `credit_approval_claim`, `risk_estimate`, `credit_score`, and `income`; widens tool names and escalation codes; new documents default to `1.1.0` |
| policy_clause | 1.1.0 | 2026-09-26 | Widens the clause family pattern (`ACC`, `CRE`, `ELG`) |
| handoff | 1.2.0 | 2026-09-27 | No field change; kept on the shared minor release |
| execution_record | 1.2.0 | 2026-09-27 | Adds optional `retrieval` (retriever, decision, threshold, top score, citations), marked `x-added-in`; widens tool names (`list_my_cards`); new documents default to `1.2.0` |
| decision | 1.2.0 | 2026-09-27 | No field change; kept on the shared minor release |
| scenario | 1.2.0 | 2026-09-27 | Widens tool names (`list_my_cards`); new documents default to `1.2.0` |
| policy_clause | 1.2.0 | 2026-09-27 | No field change; kept on the shared minor release |
| handoff | 1.3.0 | 2026-09-29 | No field change; kept on the shared minor release |
| execution_record | 1.3.0 | 2026-09-29 | Widens tool names (`list_my_credit_applications`); new documents default to `1.3.0` |
| decision | 1.3.0 | 2026-09-29 | No field change; kept on the shared minor release |
| scenario | 1.3.0 | 2026-09-29 | Widens tool names (`list_my_credit_applications`); new documents default to `1.3.0` |
| policy_clause | 1.3.0 | 2026-09-29 | No field change; kept on the shared minor release |
| scenario | 1.4.0 | 2026-09-29 | Adds optional `scripted_fallback` (the turns a simulated scenario plays when a run has no simulator model) and `template_family` (the generator family, kept within one split), marked `x-added-in`; a `tool_failure` scenario may use a `model_unavailable` fixture instead of a tool failure plan; new documents default to `1.4.0` |
| handoff, execution_record, decision, policy_clause | 1.4.0 | 2026-09-29 | No field change; they move to the shared 1.4.0 release with the scenario additions |
| execution_record | 1.5.0 | 2026-09-30 | Adds optional `llm_calls[].model_call_id`, matching the Langfuse generation span id; new documents default to `1.5.0` |
| handoff, decision | 1.5.0 | 2026-09-30 | No field change; kept on the shared output minor release; scenario and policy_clause input contracts remain at 1.4.0 |

## How to change a contract

1. Change the model, following the versioning rules above (a new field in a minor version carries `AddedIn`); bump the version in `scripts/generate_contracts.py` and the model's default `schema_version` (a test checks they match) and, for a major version, add the new file alongside the old one.
2. Run `make contracts`.
3. Update the changelog and the consumers, and commit the model, the schemas, and the consumers together.

## OpenAPI

`openapi.json` is the HTTP API contract, exported from the FastAPI app by `scripts/export_openapi.py` (`make openapi`, which also regenerates `apps/web/src/shared/api/generated/schema.d.ts` with openapi-typescript). It carries a stable `operationId` per route, the `x-roles`, `x-rate-limit`, and `x-csrf` extensions, the session cookie and CSRF header security schemes, and RFC 9457 problem responses. `services/api/tests/unit/api/test_openapi_contract.py` fails when it is stale, and `apps/web/tooling/api-types.test.ts` fails when the TypeScript types are. Versioning rules for the API are in [docs/api/README.md](../docs/api/README.md#versioning).

### Human-service API addition (2026-10-01)

Four additive HTTP operations expose customer and assigned-agent history and idempotent message sends for ADR 0026. `HumanServiceResponse`, `HumanMessage`, `HumanMessageResponse`, and `SendHumanMessageRequest` are generated in OpenAPI and the web API types. Conversation creation now returns 429 `conversation-creation-limited` with `Retry-After` after five successful customer-scoped creations in a rolling hour. New assistant turns on escalated or closed conversations return 409; accepted turn replays remain available. The existing versioned handoff, decision, and execution-record documents are unchanged.
