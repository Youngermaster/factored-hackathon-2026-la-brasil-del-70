# Pitch deck

The presentation and the animated backbone of the video pitch for the Factored AI & Data Hackathon 2026. Six main slides plus one appendix, built with [Slidev](https://sli.dev). Every slide is a canvas scene drawn in code: a click plays the scene to its next rest point, nothing moves at rest, and the PDF export shows the finished frame of every click. English only.

The scene kit, the `<Scene>` component, the seams and the check scripts are adapted from the team lead's earlier deck, VLA-introduction-slides (Apache-2.0, same author); the robot drawing helpers and the bilingual machinery were dropped.

This package is standalone. It is not part of the uv workspace or the web app, and `make check` does not build it.

## Setup and commands

Node 24 and pnpm 10.33 (`packageManager` is pinned). Run everything from `slides/`.

```bash
pnpm install
pnpm dev                 # http://localhost:3131, presenter view at /#/presenter
```

| Command | What it does |
|---|---|
| `pnpm dev` | Dev server on port 3131 with hot reload |
| `pnpm verify` | Types plus `check:content`; run before every commit |
| `pnpm check:content` | Strings, metrics, token parity, contrast, narration timing, em dashes; lists pending metrics |
| `pnpm check:content --strict` | Same, and fails while any metric is still pending |
| `pnpm check:fit` | Renders every scene at every cue and flags text outside the safe area or touching other text (dev server running) |
| `pnpm shots` | Screenshots of every slide at every click into `.shots/deck/` (dev server running) |
| `node scripts/sheet.mjs <scene>` | Contact sheet of one scene at every cue and midpoint, into `.shots/scenes/` |
| `pnpm build` | Static site into `dist/` |
| `pnpm export` | PDF with one page per click into `export/` |
| `pnpm export:final` | `check:content --strict`, then the PDF: the submission build |

The workbench is at `http://localhost:3131/#/lab`: pick a scene, scrub its playhead, jump between cues. Add `?scene_t=3.2` to a deck URL to freeze every scene at that time, or `?scene_snap` to show each click's finished frame.

## Structure

```text
slides.md               the deck skeleton: one scene per slide, click budgets, seams
scenes/<name>.ts        one scene per file: defineScene({ cues, draw })
locales/en.yml          every word on screen, one block per scene
data/metrics.yml        every number on screen, with its kind and source
lib/scene/kit.ts        canvas kit: palette C, type, kinetic words, arrows, chips
lib/scene/bank.ts       system primitives: node, tag, tab, bubble, check, hex, metricValue
lib/scene/fx.ts         colour fields, wipes, packets, rings, depth glyphs
scenes/parts/           helpers a scene splits out (<scene>-*.ts), read by check:content
lib/scene/contrast.ts   the allowed text colour pairs and their WCAG ratios
lib/metrics.ts          M('key') for scenes; lib/metric-kinds.ts for the labels
components/Scene.vue    plays a scene to the current click's cue, snaps in print mode
pages/lab.vue           the scrubber, contact sheets, and the fit probe
styles/                 tokens.css (the palette as CSS variables), base, motion
scripts/                check-content, check-fit, check-types, shots, sheet
script.md               the spoken narration, timed per section
VIDEO.md                how to record and export the video
```

| Slide | Scene | Clicks |
|---|---|---|
| 1 hook | `hook` | 4: the data field folds into the contact bar, first-contact resolution, transcripts, four workflow tiles |
| 2 thesis | `thesis` | 6: understand, decide, act and verify, injection, escalate, thesis line |
| 3 architecture | `arch` | 5: clause to Decision, request through the decorator stack, draft sent or templated, rows to quarantine, inward packets |
| 4 workflows | `workflows` | 5: account inquiry, card support, dispute, credit separation, depth grid |
| 5 evidence | `evidence` | 4: stress cases fly into the matrix, outcome tiles against B0, per workflow and language, efficiency and retrieval |
| 6 close | `close` | 3: route to operation, team on yellow, thesis bands and links |
| appendix | `appendix` | 1: profiling findings, projected cost per resolved contact |

## Colour meaning

One accent per idea, never swapped between slides. The tokens are defined once in `styles/tokens.css` and once in `C` in `lib/scene/kit.ts`; `check:content` fails when they differ.

| Token | Hex | Means |
|---|---|---|
| blue | `#3772FF` | the language model and understanding: intents, extraction, retrieval |
| yellow | `#FDC840` | deterministic code deciding and acting: rules, states, verified tools |
| red | `#E12B37` | risk: refusal, escalation, a blocked injection, the worst-served workflow |
| paper | `#E6E6E4` | data, customers, documents, text |
| ink | `#070707` | the ground |

Body-size text in blue or red uses the lighter `blueText` and `redText` tints; saturated red text is for large type only (red on ink is 4.4:1). Every allowed pair is listed in `lib/scene/contrast.ts` and checked.

The accents are used as fills, not only as strokes: filled phase headers and a yellow field that floods the verified action (thesis), filled workflow tiles and a colour grid (workflows), a half-bleed blue field for the retrieval results (evidence), a full-bleed yellow field for the team (close). One accent dominates each frame. Text on a fill is ink (`#070707`): 13.0:1 on yellow, 16.1:1 on paper, 4.8:1 on blue, and on red only at 24 px bold and up.

Two moments use the light-gray paper as the ground: the arrival of the hook (the data field that folds into the chart) and the whole architecture slide (a blueprint beat between dark slides). On paper, secondary text uses `inkDim` (9.1:1) and captions `inkMute` (5.4:1). `lib/scene/fx.ts` holds the field, wipe, packet, ring and glyph helpers.

## Editing wording

Open `locales/en.yml`, find the scene's block, and change the value. The scene redraws on save. Rules the check enforces: no em dashes; every key a scene draws must exist. YAML traps: a value containing `": "` must be quoted, and so must a value starting with `*`. Inside kinetic lines, `*asterisks*` mark the accent words.

Spoken words live in `script.md`, not in the locale file. After editing it, `pnpm check:content` prints the new duration per section.

## Updating numbers

Every number comes from `data/metrics.yml`, never from a scene or the locale file.

```yaml
eval.safe_resolution: {status: pending, kind: offline, source: "docs/evaluation/ (phase 14)"}
# becomes, once the evaluation report exists:
eval.safe_resolution: {value: 0.612, display: "61.2%", kind: offline, source: docs/evaluation/results.md}
```

- `kind` is one of `offline`, `provisional`, `projection`, `simulation`, `synthetic`. Scenes print it next to the source, because the brief requires offline measurements, simulations and projections to be labeled apart.
- `source` must be an existing path relative to the repository root once the value is filled.
- A pending metric renders as a dashed "pending" box, so a missing number is visible, never invented.
- After phase 14 lands, also update the `evidence` section of `script.md` with the numbers and their denominators.

Today 23 metrics are pending (the phase 14 evaluation and the deployment URL). `pnpm check:content` lists them.

## Exporting the PDF

```bash
pnpm export:final        # fails while any metric is pending
pnpm export              # draft PDF, pending boxes included
```

The export has one page per click of every slide, which is what makes the build-ups readable on paper. Do not add `--per-slide`: it renders one page per slide and every scene would export at its arrival frame only. For the organizers' 4 to 6 slide limit, send the six main slides and drop the appendix pages, or keep the appendix as a clearly labeled extra.

Slidev does not reliably hot-reload frontmatter: after changing `clicks:` or `transition:` in `slides.md`, restart `pnpm dev`.

## Adding a scene

1. Write `scenes/<name>.ts` with `export default defineScene({ cues, draw })`. `draw` must be a pure function of `t`: no timers, no `Math.random()` (use `rng` or `hash` from `lib/scene/math.ts`), no `Date.now()`.
2. Add a `<name>:` block to `locales/en.yml` for its words and put its numbers in `data/metrics.yml`.
3. Add the slide to `slides.md` with `layout: scene`, a unique `routeAlias`, and `clicks:` equal to `cues.length - 1`, and a `## <routeAlias>` section to `script.md`.
4. Look at `node scripts/sheet.mjs <name>`, then run `pnpm verify` and `pnpm check:fit`.
