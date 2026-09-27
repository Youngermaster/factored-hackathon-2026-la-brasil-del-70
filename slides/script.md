# Pitch narration

The spoken script for the video, one section per slide (keyed by the slide's `routeAlias` in `slides.md`) plus the two live demo segments. Words in square brackets are cues, not speech: `[click 2]` means press the right arrow once and let the scene play to its next rest before speaking the line after it.

`pnpm check:content` counts the spoken words of every section at 150 words per minute and fails when the total leaves the target range below (in seconds). The table it prints is the timing check; the shot list with timestamps is in [VIDEO.md](VIDEO.md).

<!-- total-target: 195-240 -->

Rules for editing: English, plain words, no em dashes, no number that is not in `data/metrics.yml`. When phase 14 fills the evaluation metrics, update the `evidence` section with the real numbers (the comment there marks where).

## hook

<!-- slide 1, about 30 s -->

[arrive] We ingested twenty-three and a half million rows of the organizers' synthetic bank data, under contracts.

[click 1] A third of all contacts are account inquiries. Cards and disputes are a fifth each. Credit is seven percent.

[click 2] Most contacts are resolved at first contact. Disputes are not: forty-four percent, with the worst satisfaction.

[click 3] The transcripts carry no intent: a hundred and forty-seven thousand of them, forty-two distinct texts. So routing learns from utterances we wrote and labeled.

[click 4] We built four workflows, in Spanish and Portuguese.

## thesis

<!-- slide 2, about 45 s -->

[arrive] One turn. A customer in Argentina writes: I don't recognize a charge of fifteen lucas on my card.

[click 1] The language model understands. Slang becomes fields: a new dispute, fifteen thousand pesos, an unrecognized charge.

[click 2] Deterministic code decides. Each check is a policy clause: completed, inside thirty days, a supported reason, under the automatic limit.

[click 3] Then it acts, and reports the case only after reading it back.

[click 4] Tell it to ignore its rules and block another customer's card, and nothing happens. Customer text is data; tools come from an allowlist per state.

[click 5] When a person is needed, the handoff carries verified facts and open questions, never the transcript.

[click 6] The model understands. Code decides. Evidence proves it.

## demo-dispute

<!-- live clip A, about 20 s; see VIDEO.md for what to record -->

Here is the working system. The same dispute in the chat, and beside it the agent console: the state, the rule ids, the tool call and its verification, straight from the execution record.

## architecture

<!-- slide 3, about 35 s -->

[arrive] The backend is hexagonal: the core imports nothing from the edges.

[click 1] Rules are pure functions. Clause text lives in files, in three languages.

[click 2] Every model call passes one gateway: redaction, budgets, tracing, retries, a circuit breaker. The provider is a setting.

[click 3] Every draft meets a grounding verifier. One unsupported number, and the customer gets a template instead.

[click 4] Underneath, a data platform with contracts. Bad rows are quarantined, never dropped.

[click 5] Imports flow inward, and the build fails if they don't.

## workflows

<!-- slide 4, about 35 s -->

[arrive] Four workflows, one bar.

[click 1] Account inquiries are read only, and every balance says how fresh it is.

[click 2] Card support makes the first write: a protective block with confirmation, a step-up code and a read-back.

[click 3] Disputes confirm the transaction with the customer, because the data never links a complaint to one.

[click 4] Credit keeps the risk estimate away from the model. A synthetic service decides, and there is no approved outcome at all.

[click 5] Every workflow gets clauses, a state machine, verified actions, a handoff and its own evaluation.

## demo-card

<!-- live clip B, about 15 s -->

The card block in Portuguese, with its step-up code, then a credit question answered as indicative, with reasons and a way to reach a person.

## evidence

<!-- slide 5, about 30 s. PHASE 14: replace click 2 and click 3 with the measured numbers and their denominators -->

[arrive] The baseline and the system run the same held-out cases: every workflow, both languages, all three paths.

[click 1] Including the brief's stress cases, from prompt injection to tool failures.

[click 2] We report safe automated resolution, containment, escalation quality and unsafe outcomes, with denominators.

[click 3] Always per workflow and per language.

[click 4] Retrieval is measured already: recall at one of zero point seven four, provisional.

## close

<!-- slide 6, about 20 s -->

[arrive] What we cannot claim yet: the data is synthetic, the Portuguese is ours, and our labels await review.

[click 1] Retries, fallbacks, row-level security and tracing are in place. Monitoring and load tests are next.

[click 2] We are La Brasil del 70.

[click 3] The model understands. Code decides. Evidence proves it.

## appendix-data

<!-- appendix, not narrated in the video; for questions and the PDF -->
