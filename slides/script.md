# Pitch narration

The spoken script for the video, one section per slide (keyed by the slide's `routeAlias` in `slides.md`) plus the two live demo segments. Words in square brackets are cues, not speech: `[click 2]` means press the right arrow once and let the scene play to its next rest before speaking the line after it. The three appendix slides are not narrated; their sections stay empty on purpose.

`pnpm check:content` counts the spoken words of every section at 150 words per minute and fails when the total leaves the target range below (in seconds). The table it prints is the timing check; the shot list with timestamps is in [VIDEO.md](VIDEO.md).

<!-- total-target: 195-240 -->

Rules for editing: English, plain words, no em dashes, no number that is not in `data/metrics.yml`. Names as on screen: the product is Bank Agent; the systems are P (the proposed system), B0 (the menu and rules bot) and B1 (the naive LLM agent); the team names match the README team table, and `pnpm check:content` fails when they drift.

## hook

<!-- slide 1, about 25 s -->

[arrive] Bank Agent starts from twenty-three and a half million rows of the organizers' synthetic bank data.

[click 1] A third of contacts are account inquiries. Cards and disputes are a fifth each; credit, seven percent.

[click 2] Disputes hurt most: forty-four percent resolved at first contact.

[click 3] The transcripts hold forty-two distinct texts, so routing learns from utterances we wrote.

[click 4] Four workflows, in Spanish and Portuguese.

## thesis

<!-- slide 2, about 35 s -->

[arrive] A customer in Argentina writes: I don't recognize a charge of fifteen lucas on my card.

[click 1] The language model understands. Slang becomes fields.

[click 2] Deterministic code decides. Each check is a policy clause.

[click 3] It acts, and reports the case only after reading it back.

[click 4] Tell it to block another customer's card, and nothing happens. Text is data; tools come from a per-state allowlist.

[click 5] When a person is needed, the handoff carries verified facts and open questions, never the transcript.

[click 6] The model understands. Code decides. Evidence proves it.

## demo-dispute

<!-- live clip A, about 15 s; see VIDEO.md for what to record -->

The working system: a dispute in the chat, and beside it the glass box, with the state, the rule ids, the tool call and its read-back. Then an injection, refused with no tool call.

## architecture

<!-- slide 3, about 28 s -->

[arrive] The core imports nothing from the edges.

[click 1] Rules are pure functions; clause text lives in files.

[click 2] Every model call passes one gateway: redaction, budgets, tracing, a circuit breaker. The provider is a setting: local Ollama today, a hosted model by configuration.

[click 3] One unsupported number in a draft, and a template goes instead.

[click 4] Bad rows are quarantined, never dropped.

[click 5] And the build fails if an import points outward.

## workflows

<!-- slide 4, about 27 s -->

[arrive] Four workflows, one depth bar.

[click 1] Account inquiries are read only and say how fresh each balance is.

[click 2] Card support writes: confirmation, a step-up code, a read-back.

[click 3] Disputes confirm the transaction with the customer.

[click 4] Credit keeps the risk estimate away from the model. A synthetic service decides, and no approved outcome exists.

[click 5] Every workflow gets clauses, states, verified actions, a handoff and its own evaluation.

## demo-card

<!-- live clip B, about 10 s -->

The card block in Portuguese, with its step-up code; then a credit question answered as indicative, with reasons and a way to a person.

## evidence

<!-- slide 5, about 47 s. Numbers from data/metrics.yml: the phase 14b test run, simulated on qwen2.5:7b-instruct -->

[arrive] The same three hundred and four held-out cases, three systems: ours, a menu and rules bot, and a naive LLM agent. A simulation, on a small local model.

[click 1] Per workflow first: credit is clearly ahead, and card support is not ahead of B0.

[click 2] In aggregate, fifty-eight percent safe automated resolution, against forty-two and thirteen, with fewer missed transfers. The cost is latency: two point three seconds a turn.

[click 3] Unsafe outcomes: eight for us, ninety for the naive LLM agent, mostly writes without confirmation and disclosed credit data.

[click 4] Our weak spots: three real unsafe outcomes from an echoed merchant name, and needless transfers when the model over-flags distress. The fixes are in code, not yet re-measured.

## close

<!-- slide 6, about 41 s -->

[arrive] When something fails, the service steps down: a fallback model, templates, baselines, and with the database gone, nothing. Writes never fail open.

[click 1] Every request crosses TLS, a strict content policy, secure cookies, CSRF tokens, roles, rate limits and row-level security, on one host, ready to deploy.

[click 2] We cannot claim real data, a hosted model, reviewed labels or reviewed Portuguese yet. Next: the hosted rerun, the fixes measured on dev, a real identity provider, a compliance review.

[click 3] We are La Brasil del 70: Young, Miguel Correa, David Fonseca and Julián Valencia.

[click 4] The model understands. Code decides. Evidence proves it.

## appendix-evidence

<!-- appendix, not narrated in the video; for questions and the PDF -->

## appendix-ops

<!-- appendix, not narrated in the video; for questions and the PDF -->

## appendix-data

<!-- appendix, not narrated in the video; for questions and the PDF -->
