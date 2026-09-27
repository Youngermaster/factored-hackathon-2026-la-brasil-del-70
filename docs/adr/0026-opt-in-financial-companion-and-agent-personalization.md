# 0026: Personalized financial companion features are opt-in and grounded

- Status: accepted
- Date: 2026-09-27

## Context

After the account-inquiry and human-escalation increments in [ADR 0024](0024-tuesday-account-inquiry-mvp-and-observability.md) and [ADR 0025](0025-live-agent-joins-escalated-conversation.md), the product may grow into a more personal banking companion. The intended experience could remember relevant financial context and prior customer-service conversations, offer optional financial tips or a plan, let a customer name the assistant, and show it with a pet-style image.

This direction builds on the four workflow scope in [ADR 0020](0020-four-workflows-and-the-workflow-registry.md), but adds persistent personal context and proactive financial guidance. Those features need user choice, clear evidence and freshness, strict customer isolation, and careful boundaries around investment-related guidance. The current hackathon data is synthetic and is not a basis for real financial advice.

## Considered options

1. **Keep the assistant stateless and generic.** Lowest privacy and implementation cost, but provides no continuity across account questions or service conversations.
2. **Add an opt-in, user-scoped financial memory and personalization layer with bounded guidance.** Gives customers control over continuity and optional tips while grounding responses in retrieved records and keeping personalization features simple.
3. **Build an always-on financial advisor with generated personas and proactive investment recommendations.** Most ambitious, but collects and acts on broad context by default, raises suitability and regulatory concerns, and requires image-generation and advisory services outside the intended hackathon scope.

## Decision

Choose option 2 as a future product direction. These capabilities are not part of the Tuesday release and should be added incrementally after account inquiry and human escalation are working.

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

### Assistant name and pet image

- Start with one default assistant identity/name for the product. Later, allow the customer to ask through chat to change the display name; a typed, allowlisted tool validates and stores the preference for that customer's assistant and confirms the change.
- Offer an optional pet-style assistant image. For the hackathon implementation, a typed tool returns an image identifier selected at random from a predefined, reviewed asset set. Do not build or call an image-generation service for this feature.
- Names and image choices are presentation preferences only. They do not change model access, policy, tools, or the assistant's authority.

## Consequences

- Personal memory and proactive guidance are separate opt-ins. Turning one on does not automatically enable the other.
- Persistent memory needs explicit data categories, provenance, freshness, customer controls, access isolation, and retention behavior before it can ship.
- Retrieval keeps prompts focused and supports source-grounded answers, but retrieved records may be incomplete or stale; the assistant must say so and ask, abstain, or hand off when evidence is insufficient.
- Personalized investment guidance remains gated on policy and suitability review. The hackathon prototype makes no live investment decisions or transactions.
- Name changes and pet images are lightweight, deterministic product personalization; they do not justify adding a generative image service.

## References

- [ADR 0020: Four workflows and the workflow registry](0020-four-workflows-and-the-workflow-registry.md)
- [ADR 0024: Tuesday MVP is account inquiry plus simulated human escalation](0024-tuesday-account-inquiry-mvp-and-observability.md)
- [ADR 0025: Human escalation progresses from simulated replies to a human service agent joining the conversation](0025-live-agent-joins-escalated-conversation.md)
- [Data card: intended use and data boundaries](../data/data-card.md)
