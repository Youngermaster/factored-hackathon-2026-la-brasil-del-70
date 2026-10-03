---
theme: default
title: Bank Agent
titleTemplate: '%s'
author: La Brasil del 70
info: |
  Bank Agent, by La Brasil del 70: the pitch deck for the Factored AI & Data
  Hackathon 2026. An AI-first banking customer-service system where the
  language model understands, deterministic code decides, and evidence proves it.
routeAlias: hook
layout: scene
clicks: 4
colorSchema: dark
aspectRatio: 16/9
canvasWidth: 980
routerMode: hash
selectable: false
twoslash: false
# Every ordinary boundary uses cut-left, so pressing left genuinely reverses.
# The inverse-zoom `arrive` is spent once, on the thesis.
transition: cut-left | cut-right
# Fonts are npm packages imported in styles/index.ts; `provider: none` keeps
# the deck offline (no fonts.googleapis.com request at runtime).
fonts:
  provider: none
  sans: 'Instrument Sans Variable'
  mono: 'Geist Mono Variable'
drawings:
  persist: false
---

<Scene name="hook" />

<!--
HOOK. Narration: script.md, section "hook". Click 1 share, 2 first-contact
resolution, 3 transcripts, 4 scope.
-->

---
layout: scene
routeAlias: thesis
clicks: 6
transition: arrive
---

<Scene name="thesis" />

<!--
THESIS. Narration: script.md, section "thesis". Click 1 understand, 2 decide,
3 act and verify, 4 injection, 5 escalate, 6 the thesis line.
-->

---
layout: scene
routeAlias: architecture
clicks: 5
---

<Scene name="arch" />

<!--
ARCHITECTURE. Narration: script.md, section "architecture". Click 1 policy
kernel, 2 LLM gateway, 3 grounding verifier, 4 data platform, 5 direction.
-->

---
layout: scene
routeAlias: workflows
clicks: 5
---

<Scene name="workflows" />

<!--
WORKFLOWS. Narration: script.md, section "workflows". Click 1 account inquiry,
2 card support, 3 dispute, 4 credit separation, 5 the depth bar.
-->

---
layout: scene
routeAlias: evidence
clicks: 4
---

<Scene name="evidence" />

<!--
EVIDENCE. Narration: script.md, section "evidence". Arrive: 304 cases into
P, B0, B1. Click 1 per workflow with intervals (card support flagged),
2 aggregate and trade-offs, 3 unsafe outcomes and B1's 90 by kind,
4 where P is weak. Simulation on a local open model (qwen2.5:7b-instruct).
-->

---
layout: scene
routeAlias: close
clicks: 4
---

<Scene name="close" />

<!--
CLOSE. Narration: script.md, section "close". Arrive: the degradation ladder.
Click 1 defense in depth, 2 limits and next steps, 3 team, 4 thesis and links.
-->

---
layout: scene
routeAlias: appendix-evidence
clicks: 1
---

<Scene name="appendixEvidence" />

<!--
APPENDIX A (not in the video, not one of the six main slides). Consistency
(pass^3) and language slices, then efficiency and retrieval.
-->

---
layout: scene
routeAlias: appendix-ops
clicks: 1
---

<Scene name="appendixOps" />

<!--
APPENDIX B (not in the video). One turn as a trace, then the budget guard
and the local load test.
-->

---
layout: scene
routeAlias: appendix-data
clicks: 2
---

<Scene name="appendixData" />

<!--
APPENDIX C (not in the video). Announced data problems that were absent,
the real ones profiling found, then the projected cost per resolved contact.
-->
