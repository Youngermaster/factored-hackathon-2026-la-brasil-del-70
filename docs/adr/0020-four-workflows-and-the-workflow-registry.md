# 0020: Four workflows and the workflow registry

- Status: accepted
- Date: 2026-09-26

## Context

The brief asks for depth over breadth and says that more workflows earn no bonus. Phase 02 typed one workflow (transaction disputes with an optional protective card block). On 2026-09-26 the team chose four workflows instead (CLAUDE.md section 1, `docs/plans/kickoff-notes.md`): account and payment inquiries, card support, transaction disputes, and credit information and eligibility support. The scoring risk is real: the extra workflows earn nothing by themselves, and four shallow flows would score worse than one deep one. The system also needs one place that says which workflow owns a customer's intent, so the router can dispatch it and move a conversation from one workflow to another, and so an intent outside every workflow is recognized as out of scope.

## Considered options

1. **Keep one workflow**, as the brief suggests. The lowest risk, but it overrides a team decision the working agreement already records.
2. **Four workflows with ownership implied by code**: each state machine decides which intents it accepts. Nothing checks that an intent belongs to exactly one workflow, and routing rules spread across the engine.
3. **Four workflows with an explicit registry**: a pure-data catalog in the domain that assigns every intent to exactly one workflow or marks it cross-workflow, and records each workflow's write actions, escalation-only requests, and bound clause families. A test fails when an intent has no owner.

## Decision

Option 3, implemented in `bank_agent/domain/workflow.py` (`WorkflowId`, `Intent`, `CROSS_WORKFLOW_INTENTS`) and `bank_agent/domain/workflow_catalog.py` (`WorkflowDescriptor`, `WorkflowCatalog`, `WORKFLOW_CATALOG`, `CARD_ACTION_HANDLING`), with the page [workflow-registry.md](../architecture/workflow-registry.md).

- Each of the four workflows owns its intents; `informational`, `unsupported`, `human_request`, and `greeting_or_other` are cross-workflow. The catalog rejects duplicate ids and an intent owned twice.
- `WorkflowRef.id` stays a pattern-constrained string in every contract. Registry membership is checked by the application (phase 09), not by narrowing a schema to an enum, which would be a major contract change.
- A write is allowed only when it is one of the workflow's `write_actions` and the policy matrix allows it in the current state; state names such as `START` repeat across workflows, so `PolicyRepository.get_bound` takes the workflow as well as the state.
- Card unblock and replacement requests are escalation-only: no tool performs them, because they need identity and fraud checks the prototype cannot verify.

The depth bar and the cut rule that manage the scoring risk:

- Every workflow meets the same bar: policy clauses, bound clauses per state, an explicit state machine, verified actions, a structured handoff, Spanish and Portuguese coverage, and a page in `docs/workflows/`.
- Every workflow is evaluated separately, with its own scenario slice, metrics, and failure table; aggregate numbers are never reported without the per-workflow numbers next to them.
- The shared engine, policy kernel, grounding verifier, and evaluation harness carry the engineering depth once, for all four.
- A workflow that cannot meet the bar before the deadline is cut back to clarify, abstain, or hand off, and the cut is documented as a limitation. It is never shipped shallow.

## Consequences

- The router and the engine share one source of truth for intent ownership; adding an intent without an owner fails a test.
- Every later phase carries four times the vocabulary, fixtures, scenarios, and documentation; the per-workflow reporting makes a shallow workflow visible instead of hiding it in an aggregate.
- The deviation from the brief's "depth over breadth" note is deliberate and recorded; if the depth bar cannot be met, the cut rule shrinks scope without shipping a shallow flow.
- Entry states in the catalog are placeholders for phase 09, which may change them together with the state machines.

## Follow-up decision (2026-09-27)

The proposed Tuesday scope below was superseded and was not adopted. The accepted build retains all four workflows; see resolved action 32 in [PROGRESS.md](../PROGRESS.md) and [ADR 0025](0025-tuesday-account-inquiry-mvp-and-observability.md). The internal MVP completion window is now Sunday, October 4, 2026; this does not change the accepted scope.

- **Demo access:** Verify one fixed demo credential and bind its session to one fixed demo customer and synthetic dataset.
- **Tuesday scope:** Automate account inquiry only. Card support, disputes, and credit invoke the escalation tool; a mock human service agent joins the same chat and sends a randomized, clearly labeled demo response.
- **Assistant profile:** Let the user change the assistant's name and choose another persisted PNG from the mock image service; show both in the chat header.
- **Chat limits:** Persist a unique ID per chat, allow multiple chats, and limit the fixed demo customer to five new chats per rolling 60-minute window. Keep finalized chats readable.
- **Later:** Add full customer identity and multiple profiles, plus a real human service agent who can join and exchange messages in the existing chat. See [ADR 0026](0026-live-agent-joins-escalated-conversation.md). The four-workflow scope and safe escalation requirements above remain unchanged.

Implementation note: PR 18 later added the customer-visible assistant name and predefined avatar preferences, and PR 20 added privacy-safe, metadata-only Langfuse generation export as an opt-in integration that is disabled by default. Those independently merged capabilities do not reinstate the superseded Tuesday release or its mock-human-agent design.
