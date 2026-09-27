# 0025: Human escalation progresses from simulated replies to a human service agent joining the conversation

- Status: accepted
- Date: 2026-09-27

## Context

ADR 0020 assigns human escalation paths to workflows that the prototype cannot safely resolve. ADR 0006 defines the structured, auditable handoff record. In these decisions, the **AI assistant** is the model-driven customer chat and a **human service agent** is a person handling an escalated request. For the Tuesday account-inquiry release, [ADR 0024](0024-tuesday-account-inquiry-mvp-and-observability.md) chooses a bounded simulated service responder for card-support, dispute, and credit requests to keep the first release achievable.

A generated or randomized simulated service reply demonstrates routing, but it is not human review and does not let a human service agent help the customer. The product's follow-up human escalation capability must let an authenticated human service agent join the customer's existing AI-assistant conversation and continue the exchange there.

## Considered options

1. **Treat a handoff record or simulated service reply as the completed human path.** Lowest implementation effort, but the customer never speaks to a person and the product must not imply that they did.
2. **Build a separate human-service conversation disconnected from the AI-assistant thread.** Gives human service agents a reply surface, but splits context and requires customers or staff to reconcile two conversations.
3. **Let an authenticated human service agent join the existing escalated customer conversation.** Requires a service-agent inbox, message delivery, and persistence, but preserves one conversation and a verifiable human handoff.

## Decision

Use option 3 for the live human-service-chat increment after the simulated-response release. Keep the handoff record from ADR 0006 as the structured escalation context, then allow an authorized human service agent to claim the handoff and join that same AI-assistant conversation.

- The human service-agent inbox lists pending handoffs and exposes only the request, workflow, verified facts, actions taken, evidence, and unresolved questions permitted to that service agent. It never exposes model chain-of-thought.
- Every chat has a unique, persisted conversation ID. The handoff references that ID, and customer and human service-agent messages, execution records, and lifecycle events remain attached to it. Escalation moves the existing chat into the human service-agent workflow; it never forks the customer into a separate conversation.
- Customer and human service-agent messages are delivered in both directions in the same conversation and persist across refreshes and reconnects. The customer sees whether the handoff is queued, a service agent has joined, or the conversation is disconnected or closed.
- Customers may create multiple chat threads over time, each with a distinct ID. Enforce a server-side rate limit of at most five newly created chats per authenticated customer in any rolling 60-minute window; do not impose a one-active-chat-per-customer limit. Existing chat messages do not count as new-chat creation.
- When the request is resolved, close the human service-agent connection and finalize that conversation. Keep the finalized thread readable, and let the customer start another chat subject to the rate limit.
- A successful escalation means an authorized human service agent has joined or, when none is available, the customer receives a truthful queued state and next step. A created handoff or simulated reply alone is not counted as a completed human connection.
- Messages and lifecycle events are associated with the handoff and conversation and are available for audit under the existing access controls. Any model-generated summary is clearly separate from verbatim customer and human service-agent messages.
- Verify the customer-to-human-service-agent and service-agent-to-customer paths end to end, including identity/authorization, message persistence, reconnect behavior, and no-agent availability. Keep the simulated responder explicitly labeled until this verification passes.

This decision preserves ADR 0020's four-workflow product scope. The initial release may simulate a service response while those workflow intents are routed; later increments can automate supported, low-risk intents while keeping the human service-agent path for user requests, ambiguity, missing evidence, policy-required review, and failures.

## Consequences

- The human service path becomes a real capability, not just a workflow outcome code or a handoff row.
- The human service-agent inbox and message channel are separate work from the existing handoff lifecycle and need their own API/UI, authorization, persistence, and end-to-end verification.
- Simulated service replies remain useful for routing demos and tests, but must never be represented as a human service agent's answer.

## References

- [ADR 0020: Four workflows and the workflow registry](0020-four-workflows-and-the-workflow-registry.md)
- [ADR 0006: Handoff and execution record contracts](0006-handoff-and-execution-record-contracts.md)
- [ADR 0024: Tuesday MVP is account inquiry plus simulated human escalation](0024-tuesday-account-inquiry-mvp-and-observability.md)
