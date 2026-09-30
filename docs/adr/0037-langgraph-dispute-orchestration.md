# 0037: LangGraph orchestrates the dispute workflow

- Status: proposed
- Date: 2026-09-30

## Context

The dispute workflow currently uses the shared explicit state machine, with handlers for understanding, transaction lookup, policy eligibility, reason collection, confirmation, execution, and read-back verification. The workflow is already automated, and its state and turn evidence are persisted through the conversation and execution-record repositories.

The team wants to explore autonomous specialist behavior for disputes while keeping the other three workflows unchanged. The intended specialists are a fraud supervisor and a resolution agent, with a possible ledger specialist. This proposal is a scoped exception to [ADR 0014](0014-explicit-state-machine-over-an-agent-framework.md): only dispute orchestration moves to LangGraph. The workflow registry, shared engine entry and exit, policy kernel, tools, write controls, and evidence contracts remain in force.

The current transaction and product lookup tools already provide the facts used by dispute rules. There is no separate ledger evidence service or ledger reconciliation capability in the current dispute flow. A ledger agent that only repeats those lookups would add another prompt and delegation step without adding an independent source of evidence.

## Considered options

1. **Keep dispute on the shared explicit state machine.** This preserves a single orchestration model, keeps transitions easy to enumerate, and avoids a new runtime dependency. It limits experimentation with specialist delegation and more adaptive investigation paths.
2. **Replace only dispute's internal orchestration with a LangGraph adapter.** The workflow registry continues to dispatch dispute turns through the shared engine; an adapter implementing a dispute-orchestration port coordinates bounded specialist nodes. The graph receives and returns typed dispute state, while the existing conversation repository remains the source of truth across customer turns. This adds a dependency and an adapter to maintain, but isolates the framework to one workflow and avoids a second persisted state store.
3. **Use a LangGraph supervisor package and persistent graph checkpointer for dispute.** This offers ready-made supervisor and interrupt patterns, but duplicates the app's conversation persistence and introduces checkpoint data, thread identity, retention, RLS, and consistency concerns alongside the existing unit of work. It also makes graph-library state part of the dispute persistence contract. LangChain currently recommends its [tool-based supervisor pattern](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents) for most use cases and describes [`langgraph-supervisor`](https://reference.langchain.com/python/langgraph-supervisor) as no longer actively maintained.

## Decision

Propose option 2. Compile a dispute-only graph behind a port and adapter; do not introduce LangGraph into the shared workflow engine or the account inquiry, card support, or credit workflows. The graph may coordinate these bounded roles:

- **Fraud supervisor:** gathers the required investigation findings and chooses among an explicit set of specialist tasks. It may recommend clarification or human escalation, but it cannot determine policy eligibility or make a fraud finding that authorizes an action.
- **Resolution specialist:** returns a typed recommendation for the next customer-facing step or a structured human handoff. A deterministic application handler validates the recommendation against workflow state, policy decisions, and allowed tools before acting on it.
- **Ledger specialist:** do not create a separate autonomous agent in the initial implementation. Existing transaction and product tools remain the read-only sources of those facts. Reconsider a distinct ledger node only if a separate ledger or reconciliation capability becomes available and adds evidence the current tools cannot provide.

The graph is bounded: its nodes, routes, tool capabilities, iteration count, time, and model budget are fixed by application configuration. Model output can select only a validated route from the graph's declared options. The model cannot supply a customer identifier, select arbitrary tools, or execute a write.

The graph returns typed continuation state when it needs another customer turn. That state is serialized into the existing conversation position in the same unit of work as the turn and its execution record; the application remains the source of truth across turns. Do not enable LangGraph checkpointing or long-term stores for this proposal. Customer-facing replies continue to use approved templates or grounded rendering. Policy decisions remain pure rule evaluations; writes still require the existing confirmation, step-up where required, idempotency, guarded tools, and verified read-back. Human handoffs remain structured and contain no raw transcript or hidden reasoning.

This proposal supersedes ADR 0014 only for dispute workflow orchestration if accepted. ADR 0014 remains in force for the other workflows and for the deterministic policy, tool, write, verification, and evidence controls described there.

## Consequences

- Dispute can coordinate bounded specialists without changing how the other workflows run or who owns policy decisions and writes.
- The application conversation state remains the one cross-turn persistence contract, avoiding a second checkpointer database and its RLS and retention obligations.
- The LangGraph integration needs a typed port contract, an adapter in the composition root, bounded graph execution, and tests that prove invalid model routes and tool requests cannot bypass application gates.
- The dispute graph is less enumerable than the current static transition table when routing depends on model output. Routes therefore need a closed schema, limits, traceable node results, and scenario evaluation before activation.
- The extra package and transitive dependencies increase the API supply-chain and image footprint. Before implementation, pin the chosen LangGraph release, review its license and advisories, measure the installed and image size, and record the dependency in the lockfile.
- No ledger agent is included until there is a distinct ledger capability. Adding an agent without one would duplicate existing lookups without supplying independent evidence.
- The dispute flow gains another model-coordination path, so fallback and provider-unavailable behavior must remain deterministic and fail closed for writes.
- This record is a proposal. It does not authorize implementation or a change to the current production defaults.
