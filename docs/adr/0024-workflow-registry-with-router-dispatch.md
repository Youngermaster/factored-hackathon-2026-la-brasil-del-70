# 0024: A workflow registry with router dispatch over one generic engine

- Status: accepted
- Date: 2026-09-27

## Context

The team chose four workflows (CLAUDE.md section 1, [ADR 0020](0020-four-workflows-and-the-workflow-registry.md)). Customers change topic mid-conversation ("and this charge I don't recognize"), ask things no workflow owns, or ask for a person, and every workflow must meet the same depth bar. The cut rule says a workflow that cannot meet the bar is reduced to clarify, abstain, or hand off. Session 09a builds `dispute` and `card_support`; session 09b adds `account_inquiry` and `credit`.

## Considered options

1. **One agent per workflow**, with a front classifier handing the conversation over. Each workflow owns its loop, prompts, and persistence; cross-cutting guarantees (idempotent turns, session expiry, the clarification budget, execution records) are implemented four times and drift, and a mid-flow switch has no single place that knows what is pending.
2. **One merged state machine** for all workflows. One place for everything, but the table grows with every workflow, states collide (every workflow has a START and a confirmation), and cutting a workflow means editing the shared machine.
3. **A registry of per-workflow definitions over one generic engine, with router dispatch.** The engine owns turn processing and every guarantee; each workflow is a definition validated at startup against the catalog, the bindings, the matrix, and the tools; the router maps an intent to an enabled workflow and applies the switch rules.

## Decision

Option 3. `application/engine/registry.py` builds a `WorkflowRegistry` per system (the proposed system and baseline B0) and refuses to start when an enabled workflow has no definition, a definition's intents differ from the catalog's, a state's binding state is not canonical or not bound for every country and language, an allowlist names the engine-only credit profile read, or a write tool sits in a state the policy matrix does not allow. `application/engine/router.py` dispatches: uncertain predictions get one question offering the two most likely enabled workflows; shared intents (informational, human request, greeting) are handled in any workflow; unsupported or disabled intents get a `SCOPE` clause-backed answer; a request for another workflow is confirmed first when work is pending, and the switch is recorded as `workflow_before`. `WORKFLOW_ENABLED` selects the enabled workflows, which is also how a workflow is cut back.

## Consequences

- Adding a workflow is a definition, its bindings (already present for all four), templates, and tests; the engine does not change (session 09b is the check).
- Guarantees are implemented and tested once; a bug in the engine affects every workflow, which the scenario suite across both workflows and both backends is meant to catch.
- Baseline B0 runs on the same engine with different definitions, so the phase 14 comparison isolates dialogue and understanding from policy, tools, and verification.
- The router is a keyword baseline until phase 10; routing quality bounds how often customers see the workflow question.
