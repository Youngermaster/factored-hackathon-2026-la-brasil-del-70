# bank_agent.application

## Responsibility

The application layer orchestrates: the workflow engine, the four workflows (account inquiry, card support, dispute intake and status, credit information and eligibility support), handoffs, and execution records. It calls ports, asks the policy kernel for decisions, and reports only outcomes it has verified. It never knows which adapter sits behind a port.

Phase 09 (session 09a) added the workflow engine and the first two workflows:

- `engine/`: the generic engine ([workflow router](../../../../../docs/workflows/workflow-router.md), ADRs 0014 and 0024). `definition.py` (states, transitions, handlers, allowlists, binding states), `registry.py` (startup validation against the catalog, bindings, matrix, and tools), `router.py` (dispatch and switch rules), `engine.py` (`WorkflowEngine.process_turn`: replay, session gate, language, untrusted-content checks, routing, handlers, rendering, one unit of work), `gate.py`, `flow.py`, `tools.py` (`GuardedToolset`), `decide.py` (kernel calls), `shared.py` (escalate, abstain, refuse, out of scope, informational, step-up), `handoff.py` and `summary.py`, `recorder.py` and `records.py` (execution records), `render.py`, `phrase.py`, and `templates/` (es, pt, en).
- `understanding/`: deterministic amounts and slang, relative dates, yes and no, option and language choices, and fallback slot extraction.
- `workflows/`: `dispute/`, `card_support/`, `shared/writes.py` (confirmed idempotent writes and read-backs), and `baseline/` (B0 definitions, menu router, fixed strings).

Session 09b added the last two workflows as definitions, with the engine changed only where a capability was missing:

- `workflows/account_inquiry/` ([account inquiry](../../../../../docs/workflows/account-inquiry.md)): read only; balances with the record's as-of date, payment status through the resolver and `get_payment_status`, statement summaries over a resolved period, and the `unsupported` recognizer (`ACC-ALL-3`).
- `workflows/credit/` ([credit information](../../../../../docs/workflows/credit-information.md)): catalog answers, `assessment.py` (the risk estimate and the synthetic eligibility service, kept apart), `explain.py` (the rendered `EligibilityView` and the review offers), `intake.py` (confirmation, step-up, submission, read-back), `review.py` (the `credit_review` section), and the `unsupported` recognizer (`CRE-ALL-3`).
- Engine additions: `EngineServices.credit` (`CreditPorts`: catalog, eligibility service, risk estimator), `GuardedToolset.engine_credit_profile` (the engine-only read, recorded), typed account and credit tool calls, `TurnContext.turn_values` (the profile and the estimate for one turn, never persisted), `Reply.credit` and `Reply.cite` (credit evidence for the verifier, credit fields for phrasing), `WorkflowDefinition.unsupported` with `flow.in_domain_unsupported`, `credit_review` on handoffs, and the separate record entries.
- `understanding/periods.py` (statement periods) and `understanding/slots.py` (account and credit slots).

Phases 05 and 07 added three use-case packages:

- `identity/`: `SessionService` (login, step-up with session rotation, resolution with idle and absolute expiry, logout, revocation) over the `IdentityProvider` and `SessionStore` ports, and `policy.py` with the fixed lifetimes (`docs/security/identity-and-sessions.md`).
- `tools/`: the banking tools, the only operations a workflow may use. `BankingTools.for_session(SessionContext)` returns `SessionTools` (reads for all four workflows and the three idempotent writes); `engine_only()` returns the credit profile read that no allowlist may reach; `WriteVerifier` reads every write back into a `Verification`; `ToolFailureInjector` injects timeouts, transient and permanent errors, and partial writes for tests and evaluations and is refused in production. Every call appends an audit event with redacted arguments in the same unit of work as its writes. The tools hold no policy defaults: `ToolPolicy.from_policy` takes the statement period cap (`ACC-ALL-2`), the dispute resolution target per country (`DSP-<country>-2`), and the writes that need step-up (`policies/matrix.yaml`; all three) from the policy pack.

- `grounding/` (phase 07, [grounding](../../../../../docs/workflows/grounding.md)): `BoundPolicyLookup` (the clauses of a workflow state for the verified customer's jurisdiction, every state resolved at construction), `InformationalRetrieval` and `RetrievalPolicy` (open retrieval only for the `informational` intent, threshold abstention, ELG never returned), and `GroundingVerifier` with its figure normalization (`numbers.py`), claim lexicons (`lexicon.py`), evidence collection (`evidence.py`), and models (`draft.py`: `ResponseDraft`, `GroundingContext`, `RecordFact`, `VerifiedAction`, `Violation`).

Phase 11 added the HTTP use cases:

- `conversations/service.py`: `ConversationService` (open an empty conversation with an audit event, send a turn through the engine and refuse a turn id from another conversation, the history, and the execution records for the customer or an evaluator), all scoped by the caller's session.
- `agent/inbox.py`: `AgentInbox` (list with filters, read, claim, resolve, each move audited in the same unit of work; read-only credit application intakes: every reviewable one plus any a handoff references).
- Engine: `gate.resume_after_sign_in` (a turn from a new session lineage mid-flow resumes through AUTH_REQUIRED at the last safe state; a step-up keeps the lineage), `WorkflowEngine.new_conversation`, `TurnResult.workflow`, and the account parts on `Reply` (`balances`, `payment_statuses`, `statement`).

## Who may import it

`adapters`, `api`, and `bootstrap`. The application layer imports `policy`, `ports`, and `domain` only.

## How to extend

- **Add a state.** Add its canonical name to `WorkflowDescriptor.states` and bind it in `policies/bindings.yaml` if it needs its own rules or clauses (otherwise reuse an existing binding state as its `policy_state`). Write an async handler `(TurnContext) -> Step` that reads only through `ctx.tools`, asks the kernel through `decide.evaluate`, and returns a `Reply` built from a template; add a `StateSpec` with its kind, allowlist, and (for writes) `action_policy_states`; add its exits to the transition table; add templates in es, pt, and en and a golden entry; add tests. The registry refuses the definition until the binding and the matrix agree.
- **Recognize an in-domain unsupported request.** Give the definition an `unsupported` recognizer returning an `UnsupportedRequest` (code, clause ids, template); the engine consults it before the generic out-of-scope answer and the workflow's UNDERSTAND can call it too.
- **Add a workflow.** Write a definition (`build_definition`) whose intents equal the catalog's, register its factory in `bootstrap/workflows.py` (`PROPOSED_DEFINITIONS`, and a B0 variant in `BASELINE_DEFINITIONS`), enable it with `WORKFLOW_ENABLED`, and add its page in `docs/workflows/` and scenario tests in es and pt. The engine does not change.
- **Add a tool to a workflow.** Implement it as below, then add its `ToolName` to the allowlist of the states that need it; a write also needs an action policy state that `policies/matrix.yaml` allows, a `PlannedWrite`, and a `ReadBack`.
- Add a use case as a class or function that receives its ports as constructor or call arguments, never as globals.
- Tools never accept customer identifiers from the model; the session supplies them.
- Time comes from the `Clock` port and identifiers from the `IdGenerator` port, so tests can freeze both.
- Add a tool as a `ToolCalls` method that does its work inside `_run` (one unit of work, one audit event), add it to `SessionToolset` and the failure injector, add its `ToolName`, and cover it in the tool contract suites (`tests/contracts/test_read_tools_contract.py`, `test_write_tools_contract.py`) so it runs on the memory and PostgreSQL backends. A write also needs an idempotency rule and a `WriteVerifier` read-back.

## How to test

Unit tests with in-memory adapters, `FakeLLM`, `FixedClock`, and deterministic id generators (`tests/unit/application/engine`, `understanding`). Workflow handlers need the real policy pack, so they run as in-process integration tests over the in-memory adapters and PostgreSQL through testcontainers (`tests/integration/workflows`, harness in `tests/bank_agent_workflows.py`, scenario data in `tests/bank_agent_scenarios.py`). Template goldens regenerate with `UPDATE_TEMPLATE_GOLDEN=1`. Coverage gate: 90% line coverage.
