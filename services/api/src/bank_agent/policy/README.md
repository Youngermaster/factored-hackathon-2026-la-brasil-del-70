# bank_agent.policy

## Responsibility

The policy kernel decides what the system may do. Rules are pure functions registered by rule id. The evaluator runs the rules bound to a workflow state and returns a `Decision` that names every rule id and clause version it used, so every outcome can be explained from policy rather than from model prose.

Rule parameters and the customer-facing clause text (Spanish and Portuguese) live in files under the repository `policies/` directory, not in code. Phase 06 builds the loader, the rules, and the evaluator.

## Who may import it

`application`, `adapters`, `api`, and `bootstrap`. The policy package imports only `ports` and `domain`, and the pure-core contract forbids `fastapi`, `sqlalchemy`, `httpx`, `boto3`, and `litellm`.

## How to extend

Adding a rule means three things and no workflow change:

1. a pure function registered under a new rule id in `policy/rules/`;
2. a clause file with its version and localized text under `policies/`;
3. unit tests, including Hypothesis properties for kernel invariants.

Workflow code changes only when a new state is needed.

## How to test

Unit tests under `services/api/tests/unit/policy/` with fixed clocks and in-memory inputs, plus property tests. Coverage gate: 90% line coverage.
