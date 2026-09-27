# 0014: An explicit state machine over an agent framework

- Status: accepted
- Date: 2026-09-27

## Context

The brief asks for Understand, Decide, Act, Verify, Escalate, with permissions and policy enforced outside model prose, actions reported only after verification, structured handoffs, and explanations from sources, rules, and execution records rather than hidden reasoning. The workflows write to customer records (a dispute case, a card block, later a credit intake), must know when not to act, and must behave the same way on every run so the evaluation (phase 14) measures the system rather than sampling noise. The language model provider is not chosen yet, and with `LLM_PROVIDER=fake` every model call is refused.

## Considered options

1. **A tool-calling agent loop** (the model chooses the next tool and when to stop). Little code per workflow, but the model selects tools and order; allowlists and confirmation rules must be re-checked around every call, the path through a conversation is not enumerable, tests become probabilistic, and nothing works without a provider.
2. **An agent framework graph (for example LangGraph).** Explicit nodes and edges with checkpointing, but a large dependency whose state, retries, and persistence model would duplicate the repository's unit of work, idempotency, and execution record contracts, and whose conditional edges are still easy to hand to the model.
3. **An explicit state machine in the application layer.** Each workflow is data: states, a transition table, a handler per state, a per-state tool allowlist, and the binding state that supplies its rules and clauses. The model is called only inside handlers, for understanding and optional phrasing, through typed outputs with deterministic fallbacks.

## Decision

Option 3. `application/engine/definition.py` holds `WorkflowDefinition` and `StateSpec`; the builder adds the shared exits so every move is in the table, and `check_transition` raises `WorkflowTransitionError` for anything else. Handlers ask the policy kernel for every decision, call tools through `GuardedToolset` (allowlist enforced by the engine, bounded retries for transient failures only), write with idempotency keys, and report success only after `WriteVerifier` reads the write back. One execution record per turn stores rule ids, clause versions, tool calls with verification, model and prompt versions, latency, and cost. LangGraph remains a possible future adapter: a definition could be compiled into a graph without changing the handlers, the kernel, or the contracts.

## Consequences

- Every path is enumerable and tested as a table (every illegal transition raises), and scenario tests are deterministic with `FakeLLM` or with the model refused.
- The model cannot select a tool, a state, or a customer; injection text can at most change which slots are proposed, and those are validated.
- Workflows cost more code than a prompt: each state needs a handler, templates in es and pt, and tests. The generic engine, templates, and shared write and verify steps keep the per-workflow code to understanding and state-specific decisions.
- Open-ended conversations outside the tables end in a clarifying question, an out-of-scope answer, or a handoff; that is the intended behavior, and its rate is measured in phase 14.
