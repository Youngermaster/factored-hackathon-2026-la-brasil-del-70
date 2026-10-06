# Pitch narration

The spoken script of the video pitch, in the order it is spoken. Each slide section is keyed by the slide's `routeAlias` in `slides.md`, and the live segments (`demo-*`) sit between them. On screen, every slide is the matching page of the six-page submission PDF (`export/la-brasil-del-70-pitch.pdf`, built from `pitch.md`), shown full screen, one page at a time. It is the same text as the team monologue in [docs/demo/video-monologue.md](../docs/demo/video-monologue.md), which splits it across the four speakers; `pnpm check:content` fails when the two differ by one word. The timed shot list is [docs/demo/video-plan.md](../docs/demo/video-plan.md).

Words in square brackets are not spoken. `[slide 3]` means show page 3 of the pitch PDF; `[Juan Young]` names who speaks from there on. The appendix is a separate PDF and is not narrated.

`pnpm check:content` counts the spoken words at 150 words per minute and fails when the total leaves the target range below (in seconds) or passes 3:00, the organizers' hard limit for the whole video, demo footage included. The spoken target leaves about 15 seconds of the 2:50 cut for typing and loading in the live segments.

<!-- total-target: 140-165 -->

Rules for editing: English, short spoken sentences, no em dashes, no number that is not in `data/metrics.yml`. Names as on screen: the product is Bank Agent; the systems are P (the proposed system), B0 (the menu and rules bot) and B1 (the naive LLM agent); the team names match the README team table. Edit this file and the monologue together.

## hook

<!-- video 0:00 to 0:12, pitch PDF page 1 -->

[slide 1] [Julián Valencia] A Latin American bank, twenty-three and a half million rows of data. Disputes hurt the most: only forty-four percent are solved on the first contact.

[Miguel Correa] We are La Brasil del 70, and this is Bank Agent.

## thesis

<!-- video 0:12 to 0:20, pitch PDF page 2 -->

[slide 2] [Juan Young] Our idea is simple: the model understands, the code decides. And every turn is a glass box you can inspect.

## demo-guardrail

<!-- video 0:20 to 0:38, live: out of scope, then a third-party request -->

[live] Let's try it. Who is better, Cristiano or Messi? It says no, explains what it can help with, and cites the scope rule. Another customer's credit card? Refused, under the privacy rule, and the number is never repeated.

## demo-card

<!-- video 0:38 to 1:05, live, es-MX: a protective card block -->

[David Fonseca] Now a real task, in Spanish: I lost my card, block it. The glass box shows the intent and the rules that decided. Two cards, so it asks which one. Before blocking, it asks me to confirm and sends a one-time code. It says blocked only after checking the card.

## demo-handoff

<!-- video 1:05 to 1:22, live, pt-BR: an escalation, then the agent console -->

[Miguel Correa] Now in Portuguese. This customer threatens to go to the central bank, so a person takes over, with the verified facts, not the whole transcript. In the agent console, an agent picks up the case and replies.

## demo-grafana

<!-- video 1:22 to 1:32, live: the three Grafana dashboards, about three seconds each -->

[Julián Valencia] Everything is measured. Grafana shows live traffic, outcomes, escalations, safety blocks and latency.

## architecture

<!-- video 1:32 to 2:02, pitch PDF page 3 -->

[slide 3] [Juan Young] Here is the full picture. GitHub tests every change and deploys it to one Azure VM, with a smoke test and automatic rollback. On the VM: React, FastAPI, PostgreSQL with row-level security, Qdrant, and the observability stack. Models are called through one gateway to Azure OpenAI. Inside, every turn follows the same path: router, state machine, policy, verified tools, and an execution record.

[David Fonseca] We also trained our own models. They beat the baselines offline, but not end to end, so the baselines stay the default.

## workflows

<!-- video 2:02 to 2:14, pitch PDF page 4 -->

[slide 4] [Miguel Correa] Four workflows, built to the same depth: accounts, cards, disputes and credit, each in Spanish and Portuguese. Credit never makes a lending decision.

## evidence

<!-- video 2:14 to 2:37, pitch PDF page 5 -->

[slide 5] [Julián Valencia] Does it work? Three hundred and four held-out cases, three systems, simulated on a hosted model. Per workflow, we only tie the rules bot on accounts and cards. Overall: sixty-one percent safe automated resolution, against forty-six and twenty-three. One unsafe outcome, against zero for the rules bot and ninety-two for the naive LLM agent.

## close

<!-- video 2:37 to 2:50, pitch PDF page 6; hold the last frame 2 s -->

[slide 6] [Miguel Correa] When something fails, it steps down safely, and writes never go through unverified. We do not have real bank data or human-reviewed labels yet. The model understands. Code decides. Evidence proves it.

## appendix-evidence

<!-- appendix, not in the six-slide PDF, not narrated -->

## appendix-ops

<!-- appendix, not in the six-slide PDF, not narrated -->

## appendix-data

<!-- appendix, not in the six-slide PDF, not narrated -->
