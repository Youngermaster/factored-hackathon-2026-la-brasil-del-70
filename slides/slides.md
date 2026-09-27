---
theme: default
title: Understand, decide, verify
titleTemplate: '%s'
author: La Brasil del 70
info: |
  Pitch deck for the Factored AI & Data Hackathon 2026: an AI-first banking
  customer-service system where the language model understands, deterministic
  code decides, and evidence proves it.
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
