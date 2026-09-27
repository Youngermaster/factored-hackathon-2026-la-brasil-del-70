# 0006: Handoff and execution record contracts, with no chain-of-thought field

- Status: accepted
- Date: 2026-09-26

## Context

The brief requires that a human handoff carries the request, verified facts, actions taken, supporting evidence, and unresolved questions without dumping raw transcripts, and that explanations come from sources, policy rules, and execution records rather than hidden model reasoning. The same documents are consumed by the workflow engine (phase 09), the agent inbox and glass box (phase 13), and the evaluation graders (phase 14), so their shape must be fixed early and checked mechanically.

## Considered options

1. **Free-form JSON** assembled in the workflow code. Flexible, but nothing stops a transcript or a model rationale from being added, and consumers break silently.
2. **Pydantic models in the domain as the single source of truth**, with JSON Schemas generated from them into `contracts/schemas/` and a test that fails when the committed schemas are stale.
3. **Hand-written JSON Schemas** with generated models. The schema is the source, but Python invariants (for example "a verified action needs evidence") cannot be expressed in JSON Schema and would live elsewhere.

## Decision

Option 2.

- `Handoff` (`handoff.v1.json`) carries: the schema version, handoff id, creation time, conversation and case references, the state at escalation, language, jurisdiction, the internal customer id only, auth level and expiry, a request summary and intent, verified facts each with a mandatory `table:id` source reference, actions taken each with a three-valued verification status (`verified`, `not_verified`, `mismatch`) and evidence, the policy basis as `clause_id@version` references, the escalation reason code and detail, open questions, sentiment, priority, and the SLA due time.
- Validation rules: every verified fact has a source; `verified` requires an executed action and an evidence reference; an executed action must have been confirmed; unknown keys are rejected at every level (`additionalProperties: false`), which is how transcript fields are refused; free text is length-capped, and the summary is a single paragraph, which blocks pasting a multi-turn transcript into it.
- `ExecutionRecord` (`execution_record.v1.json`) carries one turn's state before and after, outcome, intent with confidence and model version, every decision with rule ids and versions, cited clauses, tool calls with redacted arguments and verification, language model calls with tokens and cost, model and prompt versions, the policy pack version, a latency breakdown, totals that must equal the sum over the model calls, grounding violations, safety interventions, the risk tier, and the trace id.
- Neither contract, nor `Decision` (`decision.v1.json`), has a reasoning field. A test walks the generated schemas and fails on any property named like `reasoning`, `rationale`, `thought`, `chain_of_thought`, `cot`, `scratchpad`, or `inner_monologue`.
- Output contracts are generated in serialization mode, so amounts are strings and references are single strings (`transactions:T1`, `DSP-CO-2.1@3`), matching what `model_dump(mode="json")` produces. Versioning rules are in `contracts/README.md`.

## Consequences

- A handoff or record that violates the contract cannot be constructed, so the workflow cannot persist one by accident.
- Explanations in the glass box are assembled from rule results, clauses, and records; there is nothing else to show.
- Rejecting unknown keys means a newer minor version of a document fails an older validator. Producers and consumers live in one repository and regenerate together, and the README says consumers upgrade first.
- Changing a contract means changing a model, regenerating the schemas, and passing the staleness test in the same commit.
