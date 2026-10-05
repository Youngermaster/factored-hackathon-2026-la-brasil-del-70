# Pitch narration

The spoken script of the video pitch, in the order it is spoken: slide sections are keyed by the slide's `routeAlias` in `slides.md`, and the four live segments (`demo-*`) sit between them. It is the same text as the team monologue in [docs/demo/video-monologue.md](../docs/demo/video-monologue.md), which splits it across the four speakers; `pnpm check:content` fails when the two differ by one word. The timed shot list, with the exact clicks and commands, is [docs/demo/video-plan.md](../docs/demo/video-plan.md).

Words in square brackets are not spoken. `[click 2]` means press the right arrow and let the scene play to its next rest before the line after it; `[Juan Young]` names who speaks from there on. Slides without spoken lines (the thesis, the workflows, the appendix) are in the PDF, not in the video.

`pnpm check:content` counts the spoken words at 150 words per minute and fails when the total leaves the target range below (in seconds) or passes 3:00, the organizers' hard limit for the whole video, demo footage included. The spoken target leaves about 20 seconds of the 2:50 cut for typing and loading in the live segments.

<!-- total-target: 140-165 -->

Rules for editing: English, plain words, no em dashes, no number that is not in `data/metrics.yml`. Names as on screen: the product is Bank Agent; the systems are P (the proposed system), B0 (the menu and rules bot) and B1 (the naive LLM agent); the team names match the README team table. Edit this file and the monologue together.

## hook

<!-- video 0:00 to 0:14, slide 1: arrive, click 1, click 2 -->

[arrive] [Julián Valencia] A synthetic Latin American bank: twenty-three and a half million rows.

[click 1] [click 2] Disputes hurt most: only forty-four percent are resolved at first contact.

[Miguel Correa] We are La Brasil del 70, and this is Bank Agent.

## demo-guardrail

<!-- video 0:14 to 0:34, live: out of scope, then a third-party request -->

[Juan Young] This is the customer chat. On the right, the glass box records every turn. Who is better, Cristiano or Messi? It declines, lists what it can help with, and cites the scope clause. No tool ran. Another customer's credit card? Refused under the privacy clause, and the number is never repeated.

## demo-card

<!-- video 0:34 to 1:08, live, es-MX: a protective card block -->

[David Fonseca] Now a real task, in Spanish: I lost my card, block it. The model only understands. The glass box shows the intent, then the rules that decided, each tied to a policy clause. Two cards, so it asks which one instead of guessing. Before writing, it asks for confirmation and a fresh one-time code. It says blocked only after reading the card back.

## demo-handoff

<!-- video 1:08 to 1:28, live, pt-BR: an escalation, then the agent console -->

[Miguel Correa] The same engine, in Portuguese. This customer threatens to go to the central bank, so a person takes over, with verified facts and open questions, not the transcript. In the agent console, an agent claims the case and answers in the same conversation.

## demo-backend

<!-- video 1:28 to 1:46, live: the evaluator record, one Jaeger trace, the Grafana dashboard -->

[Juan Young] Behind each reply is a full execution record, and one OpenTelemetry trace from the HTTP request through the router, the policy check, the tool call and its SQL.

[Julián Valencia] Grafana turns the same telemetry into live operations: turns by workflow, outcomes, escalations, safety interventions and latency.

## architecture

<!-- video 1:46 to 2:12, slide 3: arrive, clicks 1 to 3 -->

[arrive] [Juan Young] FastAPI with a hexagonal core, React, and PostgreSQL with row-level security.

[click 1] It runs on one VM: Docker Compose behind Caddy, with the observability stack beside it.

[click 2] Every model call passes one LiteLLM gateway, so the provider is a setting.

[click 3] [David Fonseca] Our learned router, resolver and risk estimator beat their baselines offline, but not end to end, so the baselines stay the default.

## evidence

<!-- video 2:12 to 2:36, slide 5: arrive, clicks 1 to 3. Numbers from data/metrics.yml: the hosted test run, simulated on azure/gpt-4.1-mini -->

[arrive] [Julián Valencia] Three hundred and four held-out cases, three systems, simulated on a hosted model.

[click 1] Per workflow first: card support ties the menu and rules bot.

[click 2] In aggregate, sixty-one percent safe automated resolution, against forty-six and twenty-three.

[click 3] One graded unsafe outcome, a confirmed second write, against ninety-two for the naive LLM agent.

## close

<!-- video 2:36 to 2:50, slide 6: arrive, then cut to click 2 and click 4 -->

[arrive] [Miguel Correa] When something fails, it steps down, and writes never fail open.

[click 2] We cannot claim real data or human-reviewed labels yet.

[click 4] The model understands. Code decides. Evidence proves it.

## thesis

<!-- slide 2, in the PDF; not narrated in the video (the live segments show the same loop) -->

## workflows

<!-- slide 4, in the PDF; not narrated in the video (the live segments play two of the four workflows) -->

## appendix-evidence

<!-- appendix, not in the six-slide PDF, not narrated -->

## appendix-ops

<!-- appendix, not in the six-slide PDF, not narrated -->

## appendix-data

<!-- appendix, not in the six-slide PDF, not narrated -->
