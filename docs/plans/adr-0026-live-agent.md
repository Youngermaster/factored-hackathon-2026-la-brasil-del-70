# ADR 0026: live human service in the existing conversation

## Review baseline

Reviewed on 2026-10-01 against GitHub main at `2bcdf79`, in the isolated branch `feat/adr-0026-live-agent`. The original checkout remains on its existing branch with its uncommitted card-support, seed, test, script, and documentation changes preserved.

The phase log marks phases 00 through 17 complete. That does not mean every accepted product direction is implemented. [ADR 0026](../adr/0026-live-agent-joins-escalated-conversation.md) is the next product increment: an authenticated human service agent joins the customer's existing conversation. ADRs 0027 and 0028 follow it. Deployment and submission remain separate pending actions, with the internal completion window ending October 4 and the official submission closing October 5.

ADR 0025 is superseded on the remote baseline. Assistant preferences and the opt-in, metadata-only Langfuse export landed independently; all four workflows remain automated. PR 25 also landed evaluation and security fixes. Published evaluation results still describe their recorded run, not a measurement of this baseline.

## Pull request review

GitHub was accessible through the configured SSH remote. Public REST access returned 404, and no authenticated REST client was available. PR head and merge references were downloaded into the separate review clone. A merge reference is evidence of GitHub's merge preview, not authoritative confirmation of a PR's open status, reviews, checks, or approval.

| PR                                                                                      | Reviewed changes                                                             | Implication                                                                                                                             |
| --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| [21](https://github.com/Youngermaster/factored-hackathon-2026-la-brasil-del-70/pull/21) | Proposed ADR 0037 (first numbered 0036): Azure Key Vault with managed identity; documentation only | Conditional on selecting Azure. Do not add Azure dependencies or change secret loading before that decision.                            |
| [23](https://github.com/Youngermaster/factored-hackathon-2026-la-brasil-del-70/pull/23) | Proposed ADR 0037: dispute-only LangGraph orchestration; documentation only  | The record explicitly does not authorize implementation or default changes. Keep the current explicit state machine for this increment. |

These were the two fetched PR merge references. Their heads contain commits outside main. Confirm the current open list, discussions, and CI with authenticated GitHub access before claiming the GitHub review complete. ADR numbers 0036 and 0037 are already claimed by these proposals; do not reuse them.

## Existing behavior and missing capability

| Requirement                                             | Existing evidence                                                                                          | Remaining work                                                                                                              |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Persisted conversation identity                         | `domain/conversation.py`, `application/conversations/service.py`                                           | Keep the same identity through human service.                                                                               |
| Structured escalation and authorized claim              | `domain/handoff.py`, `application/agent/inbox.py`                                                          | Connect claim and resolution to conversation lifecycle atomically.                                                          |
| Human messages in both directions                       | `api/routers/agent.py` currently exposes handoff and credit operations, not a conversation message channel | Add persisted human-service messages and authorized read/write operations.                                                  |
| Queued, joined, disconnected, closed visibility         | Conversation status currently has active, escalated, and closed values                                     | Define human-service lifecycle events and truthful UI states. Transport failure must not imply the agent has left.          |
| Five newly created chats per customer in a rolling hour | Creation currently uses the general WRITE rate class, whose limits are per minute and per IP/session       | Add an atomic customer-scoped rolling limit shared across workers and sessions. Existing chat messages must not consume it. |
| Readable closed conversation and reconnect              | Customer history exists                                                                                    | Persist message order and lifecycle; reject new messages after closure; resume delivery from a cursor.                      |

## Implementation increments

1. Define typed human-service messages, lifecycle events, repository operations, and authorization invariants. Keep existing assistant turns and execution records intact. The claimed agent can read the structured handoff and the authorized human-service exchange; do not grant general access to a customer's earlier transcript, credit profile, or evaluator records.
2. Implement memory and PostgreSQL persistence with a shared contract suite. Allocate the migration number from current main immediately before writing it; the reviewed baseline ends at 0013. Customer tables need forced RLS, minimal grants, retention behavior, stable message ordering, and concurrency protection for claim, send, and close.
3. Connect handoff claim, customer messages, agent replies, and resolution in application services. A queued conversation accepts customer follow-ups without another assistant action. Once claimed, replies come from the authorized agent. Close the handoff and conversation together; preserve readable history.
4. Enforce the creation quota by customer identity using a database transaction and serialized counting of successful creations in the previous hour. Test simultaneous requests, separate sessions, the exact time boundary, independent customers, and failed creations. The existing per-minute request limiter is not a substitute.
5. Add customer and agent API operations with role declarations, CSRF, request limits, allowlisted responses, idempotent message IDs, and 404 for resources outside the caller's authorization. Regenerate OpenAPI and web types; update the endpoint catalog and contract versions where required.
6. Add customer lifecycle labels and agent reply controls through existing feature boundaries. Use TanStack Query polling with a message cursor for the first delivery increment; show connection errors separately from persisted lifecycle state. Persisted ordering and refetch after reconnect provide continuity without adding a transport dependency. Add all copy in es, pt, and en.
7. Verify the complete customer-to-agent and agent-to-customer exchange through HTTP and feature integration tests, including no-agent availability, refresh, reconnect, closure, isolation, and a customer opening another thread within the quota. Run `make check` before marking the capability complete.

## Files and documentation

Implementation touches the API domain, repository ports, memory and PostgreSQL adapters, composition root, conversation and inbox services, API schemas and routers, generated contracts, and the conversation and agent-inbox web features. Read their package READMEs before each increment.

Update the API endpoint catalog, frontend feature documentation, handoff workflow documentation, security isolation and retention documentation, contract changelog, and PROGRESS with the delivered increment and its actual validation. Do not mark ADR 0026 built until the full exchange passes. The deployment and submission checklists keep their outstanding human actions.

## Risks and validation

- Claim and close races require database enforcement, not just UI controls.
- Human text is untrusted content and renders as plain text. Sending a human message does not authorize banking tools or write actions.
- Staff access must remain bounded by the claimed handoff; customer history access remains scoped to the authenticated customer.
- Message retention must follow the existing conversation-text policy while immutable audit evidence remains intact.
- The rolling-hour quota must survive session changes and concurrent workers without imposing a one-active-chat limit.
- The new UI and application behavior require fresh development evidence; historical evaluation numbers must not be relabeled as current results.

The implementation now covers these increments in the isolated `feat/adr-0026-live-agent` branch. It uses a separate `human_messages` table attached to the existing conversation and handoff, leaving legacy mixed-role messages intact. Focused memory/PostgreSQL contracts, HTTP exchanges and production-role checks have passed. The full `make check` gate passed, including unit, integration, coverage, web, documentation and security checks. The delivered state and exact verification are recorded in PROGRESS.
