# Pitch deck

The presentation and the animated backbone of the video pitch for Bank Agent, La Brasil del 70's entry to the Factored AI & Data Hackathon 2026. Six main slides (the submission PDF) plus three appendix slides (a separate PDF), built with [Slidev](https://sli.dev). Every slide is a canvas scene drawn in code: a click plays the scene to its next rest point, nothing moves at rest, and the PDF export shows the finished frame of every click. English only.

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
| `pnpm check:content` | Strings, metrics, intervals, token parity, contrast, narration timing (fails past the 3:00 video limit), parity with the team monologue, the six-slide export range, em dashes, naming; lists pending metrics |
| `pnpm check:content --strict` | Same, and fails while any metric is still pending or any placeholder remains |
| `pnpm check:fit` | Renders every scene at every cue and flags text outside the safe area or touching other text (dev server running) |
| `pnpm shots` | Screenshots of every slide at every click into `.shots/deck/` (dev server running) |
| `node scripts/sheet.mjs <scene>` | Contact sheet of one scene at every cue and midpoint, into `.shots/scenes/` |
| `pnpm build` | Static site into `dist/` |
| `pnpm export` | The six main slides as a PDF, one page per click, into `export/la-brasil-del-70-pitch.pdf` |
| `pnpm export:appendix` | The three appendix slides as their own PDF, `export/la-brasil-del-70-appendix.pdf` |
| `pnpm export:final` | `check:content --strict`, then `pnpm export`: the submission build |

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
scripts/                check-content (with narration.ts), check-fit, check-types, shots, sheet
script.md               the spoken narration of the 3:00 video, by segment and speaker
VIDEO.md                how to record and export the video (the shot list is docs/demo/video-plan.md)
```

| Slide | Scene | Dimension tag | Clicks |
|---|---|---|---|
| 1 hook | `hook` | Data Analytics, Data Engineering | 4: the data field folds into the contact bar, first contact resolution, the pipeline with quarantine and three real data problems with the decision each forced, four workflow tiles |
| 2 thesis | `thesis` | Technical Judgment, AI Engineering | 6: understand, decide, act and verify, injection, escalate, thesis line |
| 3 architecture | `arch` | AI Engineering, Machine Learning, Technical Judgment | 3: arrive on the stack around the hexagonal core; the deployment on one Azure VM behind Caddy with the obs profile and the managed path; one turn model by model with the risk estimate bouncing off the wall; learned components against their baselines and the decision to keep the baselines |
| 4 workflows | `workflows` | AI Engineering, Technical Judgment | 5: account inquiry, card support, dispute, credit separation, depth grid |
| 5 evidence | `evidence` | Machine Learning, Data Analytics | 4: arrive with 304 cases into P, B0 and B1; per workflow with intervals, the aggregate and the trade-offs, unsafe grids with B1's 90 by kind, P's weak spots |
| 6 close | `close` | Technical Judgment, AI Engineering | 4: arrive on the degradation ladder; defense in depth on the deployed host, limits and next steps, team on yellow, thesis bands and links |
| appendix A | `appendixEvidence` | none | 1: pass^3 and the language slices, then efficiency and retrieval |
| appendix B | `appendixOps` | none | 1: one turn as a trace, then the budget guard and the load test |
| appendix C | `appendixData` | none | 2: announced problems measured at zero, what profiling found, projected cost per resolved contact |

The six main slides cover the organizers' five evaluation dimensions between them, and each carries a small tag top-right naming the ones it answers (`dims` in each scene's locale block, drawn by `dims()` in `lib/scene/bank.ts`). The appendix slides carry an "appendix" eyebrow, are not narrated, and are not in the submission PDF. The video narrates slides 1, 3, 5, and 6; slides 2 and 4 are in the PDF, and the live segments show the same loop.

## Colour meaning

One accent per idea, never swapped between slides. The tokens are defined once in `styles/tokens.css` and once in `C` in `lib/scene/kit.ts`; `check:content` fails when they differ.

| Token | Hex | Means |
|---|---|---|
| blue | `#3772FF` | the language model and understanding: intents, extraction, retrieval |
| yellow | `#FDC840` | deterministic code deciding and acting: rules, states, verified tools |
| red | `#E12B37` | risk: refusal, escalation, a blocked injection, the worst-served workflow |

On the evidence slides the three systems keep one colour each: P yellow (code decides), B0 light gray (`dim`, the baseline), B1 blue (the model alone); unsafe outcomes are red whichever system produced them.
| paper | `#E6E6E4` | data, customers, documents, text |
| ink | `#070707` | the ground |

Body-size text in blue or red uses the lighter `blueText` and `redText` tints; saturated red text is for large type only (red on ink is 4.4:1). Every allowed pair is listed in `lib/scene/contrast.ts` and checked.

The accents are used as fills, not only as strokes: filled phase headers and a yellow field that floods the verified action (thesis), filled workflow tiles and a colour grid (workflows), a half-bleed blue field for the retrieval results (evidence), a full-bleed yellow field for the team (close). One accent dominates each frame. Text on a fill is ink (`#070707`): 13.0:1 on yellow, 16.1:1 on paper, 4.8:1 on blue, and on red only at 24 px bold and up.

Two moments use the light-gray paper as the ground: the arrival of the hook (the data field that folds into the chart) and the whole architecture slide (a blueprint beat between dark slides). On paper, secondary text uses `inkDim` (9.1:1) and captions `inkMute` (5.4:1). `lib/scene/fx.ts` holds the field, wipe, packet, ring and glyph helpers.

## Editing wording

Open `locales/en.yml`, find the scene's block, and change the value. The scene redraws on save. Rules the check enforces: no em dashes; every key a scene draws must exist. YAML traps: a value containing `": "` must be quoted, and so must a value starting with `*`. Inside kinetic lines, `*asterisks*` mark the accent words.

Spoken words live in `script.md`, not in the locale file, and the same words, split by speaker, in `docs/demo/video-monologue.md`: edit both, then `pnpm check:content` prints the duration per section and per speaker and fails if the two differ or the total passes 3:00.

## Updating numbers

Every number comes from `data/metrics.yml`, never from a scene or the locale file.

```yaml
deploy.url: {status: pending, kind: offline, source: "deploy/README.md (phase 16)"}
# becomes, once the human deploys:
deploy.url: {value: "https://...", kind: offline, source: deploy/README.md}

# a rate with its interval, and a count with its denominator:
eval.sar.all.p: {value: 58.2, display: "177/304", lo: 53, hi: 64, kind: simulation, source: docs/evaluation/results.md}
eval.unsafe.p: {value: 8, of: 304, display: "8 of 304", lo: 1.1, hi: 5.1, kind: simulation, source: docs/evaluation/results.md}
```

- `kind` is one of `offline`, `provisional`, `projection`, `simulation`, `synthetic`. Scenes print it next to the source, because the brief requires offline measurements, simulations and projections to be labeled apart. The evidence slides print "simulation on a local open model (qwen2.5:7b-instruct)".
- `source` must be an existing path relative to the repository root once the value is filled.
- `lo` and `hi` are the 95% interval in percent (Wilson for rates, exact for unsafe outcomes), `of` the denominator of a count. The check fails when an interval does not contain its estimate or a fraction does not match its value.
- A pending metric renders as a dashed "pending" box, so a missing number is visible, never invented.
- If the evaluation is rerun (BACKLOG 14c: a hosted model, the 14c fixes), refresh the `eval.*` block from `docs/evaluation/results.md` and the `evidence` section of `script.md` with it.

Today no metric is pending: `deploy.url` holds the demo URL from the README. `pnpm check:content` lists anything pending.

## Naming

One name per thing, everywhere in the deck, the narration and the video guide:

- the product is Bank Agent, the name in the app header (`app.name` in `apps/web/src/shared/i18n/locales/*.json`);
- the team is La Brasil del 70, and each member's name and role on the close slide match the README team table (`pnpm check:content` fails when a name on the slide is missing from `script.md` or the README);
- the systems are P (the proposed system), B0 (the menu and rules bot) and B1 (the naive LLM agent), and the metrics and workflow names are those of `docs/evaluation/results.md`; the degradation levels are L0 to L4 as in `docs/operations/degradation.md`.

`scripts/check-content.ts` lists the known variant spellings it rejects, with the canonical form for each. A placeholder such as `[confirm ...]` in the locale file or the script is a warning while drafting and an error under `--strict`, so it cannot reach the submission PDF.

## Exporting the PDF

```bash
pnpm export:final        # the submission PDF: six main slides, fails while any metric is pending
pnpm export              # the same six slides as a draft, pending boxes included
pnpm export:appendix     # the three appendix slides, a separate PDF
```

`pnpm export` uses `--range 1-6`, so the submission PDF holds only the six main slides (32 pages, one per click, which keeps the build-ups readable on paper); `export:appendix` uses `--range 7-9` (7 pages). `pnpm check:content` fails if a range stops matching the deck. Do not add `--per-slide`: every scene would export at its arrival frame only.

Slidev does not reliably hot-reload frontmatter: after changing `clicks:` or `transition:` in `slides.md`, restart `pnpm dev`.

## Adding a scene

1. Write `scenes/<name>.ts` with `export default defineScene({ cues, draw })`. `draw` must be a pure function of `t`: no timers, no `Math.random()` (use `rng` or `hash` from `lib/scene/math.ts`), no `Date.now()`.
2. Add a `<name>:` block to `locales/en.yml` for its words and put its numbers in `data/metrics.yml`.
3. Add the slide to `slides.md` with `layout: scene`, a unique `routeAlias`, and `clicks:` equal to `cues.length - 1`, and a `## <routeAlias>` section to `script.md`.
4. Look at `node scripts/sheet.mjs <name>`, then run `pnpm verify` and `pnpm check:fit`.
