# 0027: Financial memory and guidance are opt-in and grounded

- Status: accepted
- Date: 2026-09-27

## Context

Financial memory, tips, and planning remain optional future directions beyond the current internal MVP completion window. The narrower Tuesday release in [ADR 0025](0025-tuesday-account-inquiry-mvp-and-observability.md) was superseded and its assistant-profile feature was not adopted. Current scope and status are recorded in [ADR 0020](0020-four-workflows-and-the-workflow-registry.md) and [PROGRESS.md](../PROGRESS.md).

This direction builds on the four workflow scope in [ADR 0020](0020-four-workflows-and-the-workflow-registry.md), but adds persistent personal context and proactive financial guidance. Those features need user choice, clear evidence and freshness, strict customer isolation, and careful boundaries around investment-related guidance. The current hackathon data is synthetic and is not a basis for real financial advice.

## Considered options

1. **Keep the assistant stateless and generic.** Lowest privacy and implementation cost, but provides no continuity across account questions or service conversations.
2. **Add opt-in, user-scoped financial memory and bounded guidance.** Gives customers control over continuity and optional tips while grounding responses in retrieved records.
3. **Build an always-on financial advisor with proactive investment recommendations.** This collects and acts on broad context by default and raises suitability and regulatory concerns.

## Decision

Choose option 2 as a future product direction. These capabilities are not part of the revised internal MVP completion window and should be added only through later scope decisions.

### User-controlled financial memory

- Offer an explicit opt-in for personalized memory and explain what categories it uses, such as customer-approved account/product summaries and relevant prior service conversations. Do not describe the assistant as having unrestricted knowledge of a customer.
- Use short-term conversation context for the current chat and, when the customer opts in, retrieve only the relevant user-scoped records or summaries for a later conversation (for example, through a bounded RAG layer). Do not load or send the entire financial history to the model by default.
- Every retrieved fact carries its source and as-of time. The customer can inspect, correct, clear, or disable remembered context. Disabling or clearing memory stops future retrieval and removes the customer-controlled memory artifacts according to the retention policy; it does not erase immutable audit records required by the existing contracts.
- Customer access remains enforced in the service and retrieval layer. Memory and retrieved material are evidence supplied to the assistant, not instructions; they cannot override policy or authorize an action.

### Optional financial tips and plans

- Let customers separately opt in to financial tips, periodic notifications, or a personalized planning experience. They choose the topics and cadence, can pause or stop notifications, and receive no proactive financial notification by default.
- Ground suggestions in the customer's authorized, current data and explain the relevant sources, assumptions, and uncertainty. Distinguish educational information and budgeting guidance from a decision, guarantee, or executed financial action.
- Investment-related content requires a separately reviewed policy and appropriate suitability and jurisdiction controls before the product makes personalized recommendations about what a customer should invest in. Until then, provide general educational information or hand off; never place a trade or imply a guaranteed return.
- The hackathon prototype may demonstrate these ideas only with synthetic data and clearly labeled examples, not as a real financial plan or investment recommendation.

## Consequences

- Personal memory and proactive guidance are separate opt-ins. Turning one on does not automatically enable the other.
- Persistent memory needs explicit data categories, provenance, freshness, customer controls, access isolation, and retention behavior before it can ship.
- Retrieval keeps prompts focused and supports source-grounded answers, but retrieved records may be incomplete or stale; the assistant must say so and ask, abstain, or hand off when evidence is insufficient.
- Personalized investment guidance remains gated on policy and suitability review. The hackathon prototype makes no live investment decisions or transactions.
- Assistant name and PNG-image preferences from the superseded ADR 0025 plan were not adopted and are not part of the current product scope.

## References

- [ADR 0020: Four workflows and the workflow registry](0020-four-workflows-and-the-workflow-registry.md)
- [ADR 0025: superseded historical Tuesday MVP plan](0025-tuesday-account-inquiry-mvp-and-observability.md)
- [ADR 0026: Human escalation progresses from simulated replies to a human service agent joining the conversation](0026-live-agent-joins-escalated-conversation.md)
- [Data card: intended use and data boundaries](../data/data-card.md)
