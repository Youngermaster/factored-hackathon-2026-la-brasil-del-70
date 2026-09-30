# Design system

The web app's visual and interaction rules. Tokens live in `apps/web/src/shared/ui/tokens.css`, primitives in `apps/web/src/shared/ui/`, usage in [`docs/frontend/components.md`](../frontend/components.md), and the decision record in [ADR 0018](../adr/0018-design-system.md). The pre-flight audit is in [`audit.md`](audit.md).

## Direction

Design read: a trust-first banking product UI (a customer chat on mobile and desktop, agent and evaluator consoles on desktop), with a calm, precise language, built on Radix primitives and Tailwind v4 tokens, sharing one visual identity with the team's pitch deck (`slides/`), so the demo and the video read as one product.

The direction was pre-approved by the orchestrator under the human's delegation (see `docs/plans/phase-12.md`): the deck's "Azure Skies" palette and its three typefaces, adapted with restraint. The deck is dark and loud because it is a stage; the app is light by default and quiet because it is a bank.

Dials (from the phase brief): `DESIGN_VARIANCE` 4, `MOTION_INTENSITY` 2, `VISUAL_DENSITY` 5 for customer surfaces and 7 for the consoles.

## Principles

1. **Color means something, or it is not there.** The thesis of the product ("the language model understands, deterministic code decides, evidence proves it") is the color system:

   | Accent | Hex | Means | Where it may appear |
   |---|---|---|---|
   | Blue (understanding) | `#3772FF` | The language model: intents, extracted fields, retrieval | Model-derived labels and trace steps |
   | Yellow (decision) | `#FDC840` | Deterministic rules and verified actions | The `verified` status, a verified-action confirmation, rule steps in a trace |
   | Red (risk) | `#E12B37` | Refusal, escalation, failure | Errors, escalations, failed actions |
   | Light gray (paper) | `#E6E6E4` | Data and documents | Sunken surfaces that hold records, the demo code, skeletons |
   | Ink | `#070707` | The ground and the text | Text, the primary action, the dark theme ground |

   One accent at a time on a screen region. The primary action is ink, never an accent: an accent on a button would claim a meaning the button does not have.
2. **Calm before clever.** Generous spacing, a light theme by default, no gradients, no glass, no glow, no decorative motion. A customer reading a balance or a refusal should not have to fight the interface.
3. **Say it in words; color repeats it.** Every state has text and an icon; color never carries meaning alone (WCAG 1.4.1).
4. **Precise about what is known.** Balances show their as-of instant, amounts are exact decimals, and eligibility is an indication, never an approval.
5. **Keyboard and screen reader first.** Visible focus everywhere, one landmark per role, live regions for what changes on its own.

## Typography

Self-hosted through `@fontsource-variable` packages (no font CDN, so the strict CSP holds), the same three families the deck loads:

| Role | Family | Use | Why |
|---|---|---|---|
| Display | Unbounded Variable, weight 600 | The product name and page titles (`h1`) only | The deck's display face: it carries the identity, so it is rationed to one line per page |
| Text and UI | Instrument Sans Variable, 400 to 600 | Everything else | The deck's body face: a legible grotesque with enough character to avoid the Inter default |
| Figures and codes | Geist Mono Variable | Amounts, one-time codes, identifiers, latencies, countdowns | Monospaced figures are tabular, so amounts align; codes read digit by digit |

Scale (Tailwind tokens in `src/index.css`):

| Token | Size / line height | Use |
|---|---|---|
| `text-display` | 32 / 40 px | Page title (Unbounded) |
| `text-heading` | 24 / 32 px | Step titles, console page titles, digit boxes |
| `text-title` | 20 / 28 px | Card and dialog titles |
| `text-lead` | 18 / 28 px | Page introductions |
| `text-body` | 16 / 24 px | Body copy, inputs (16 px avoids zoom on iOS) |
| `text-small` | 14 / 20 px | Labels, hints, table cells, secondary text |
| `text-caption` | 12 / 16 px | Badges, meta, the persona id |

Body line length is capped at about 65 characters (`max-w-prose`, `max-w-2xl`). No text is smaller than 12 px.

## Spacing, radii, layout

- **Spacing:** Tailwind's 4 px scale, used in the steps 4, 8, 12, 16, 24, 32, 48 px (`Stack` and `Inline` expose exactly these as `gap` 1, 2, 3, 4, 6, 8, 12). Customer pages use 32 to 48 px between sections; the consoles use 24 to 32 px.
- **Radii (one rule, applied everywhere):** controls (buttons, inputs, badges, digit boxes) 6 px (`rounded-control`); containers (cards, dialogs, toasts, tables) 12 px (`rounded-card`); status pills and the timeline markers are fully round, and nothing else is.
- **Layout:** the customer surface is one centered column, max 1024 px, chat-first, with the glass box beside it on wide screens (phase 13). The console is a 224 px sidebar plus content on wide screens and a navigation row under the header on narrow ones. Every multi-column layout collapses to one column below 640 px (`sm`) or 1024 px (`lg`).
- **z-index scale:** header 30, overlays 40, dialog, sheet, tooltip, and toast content 50. Nothing else sets one.

## Color tokens

Every color is an explicit opaque hex (alpha chains make contrast unverifiable); the overlay scrim is the only translucent value and never sits behind text. Tailwind's default palette is removed (`--color-*: initial`), so only these tokens exist as utilities (`bg-surface`, `text-fg-muted`, `border-border-strong`, ...).

| Token | Light | Dark | Role |
|---|---|---|---|
| `canvas` | `#F3F3F1` | `#070707` | Page ground |
| `surface` | `#FFFFFF` | `#121212` | Cards, header, dialogs, inputs |
| `surface-sunken` | `#E6E6E4` | `#1F1F1F` | Paper: records, the demo code, skeletons, the active nav item |
| `surface-hover` | `#ECECEA` | `#1A1A1A` | Hover fill |
| `border` | `#D9D9D6` | `#2E2E2E` | Decorative hairlines, never load-bearing |
| `border-strong` | `#7A7A77` | `#7A7A77` | Input and control boundaries (3:1 on every surface) |
| `fg` / `fg-secondary` / `fg-muted` | `#070707` / `#3A3A38` / `#5C5C59` | `#E6E6E4` / `#B8B8B5` / `#8C8C89` | Text, secondary text, hints and captions |
| `action` / `action-fg` | `#070707` / `#FFFFFF` | `#E6E6E4` / `#070707` | Primary button, tooltip |
| `focus` | `#070707` | `#E6E6E4` | 2 px focus outline, 2 px offset |
| `understanding` / `-text` / `-subtle` | `#3772FF` / `#2A57C9` / `#EAF0FF` | `#3772FF` / `#6F9BFF` / `#0E1A3A` | Model-derived content |
| `decision` / `-text` / `-subtle` | `#FDC840` / `#070707` / `#FFF4D1` | `#FDC840` / `#FDC840` / `#2B2208` | Verified actions and rules; text on yellow is always ink |
| `risk` / `-fg` / `-text` / `-subtle` | `#E12B37` / `#FFFFFF` / `#B4202B` / `#FCEBEC` | `#E12B37` / `#FFFFFF` / `#F0616A` / `#2E0B0E` | Errors, refusals, escalations |

### Contrast (computed; enforced by `tokens.test.ts`)

`apps/web/src/shared/ui/contrast.ts` lists every allowed foreground and background pair with its minimum (4.5:1 for text, 3:1 for control boundaries and focus indicators, WCAG 2.2 SC 1.4.3 and 1.4.11); the test reads `tokens.css` and fails when any pair in either theme drops below. A selection:

| Pair | Light | Ratio | Dark | Ratio |
|---|---|---|---|---|
| `fg` on `canvas` | #070707 on #f3f3f1 | 18.13 | #e6e6e4 on #070707 | 16.12 |
| `fg` on `surface` | #070707 on #ffffff | 20.14 | #e6e6e4 on #121212 | 14.99 |
| `fg-secondary` on `surface` | #3a3a38 on #ffffff | 11.40 | #b8b8b5 on #121212 | 9.42 |
| `fg-muted` on `canvas` | #5c5c59 on #f3f3f1 | 6.04 | #8c8c89 on #070707 | 5.97 |
| `fg-muted` on `surface-sunken` | #5c5c59 on #e6e6e4 | 5.37 | #8c8c89 on #1f1f1f | 4.89 |
| `understanding-text` on `surface` | #2a57c9 on #ffffff | 6.35 | #6f9bff on #121212 | 6.97 |
| `risk-text` on `surface` | #b4202b on #ffffff | 6.60 | #f0616a on #121212 | 5.91 |
| `border-strong` on `surface-sunken` (3:1) | #7a7a77 on #e6e6e4 | 3.44 | #7a7a77 on #1f1f1f | 3.83 |
| `focus` on `canvas` (3:1) | #070707 on #f3f3f1 | 18.13 | #e6e6e4 on #070707 | 16.12 |
| `action-fg` on `action` | #ffffff on #070707 | 20.14 | #070707 on #e6e6e4 | 16.12 |
| `decision-fg` on `decision` (ink on yellow) | #070707 on #fdc840 | 12.96 | same | 12.96 |
| `understanding-fg` on `understanding` | #070707 on #3772ff | 4.81 | same | 4.81 |
| `risk-fg` on `risk` | #ffffff on #e12b37 | 4.56 | same | 4.56 |
| `risk-text` on `risk-subtle` | #b4202b on #fcebec | 5.73 | #f0616a on #2e0b0e | 5.66 |
| `understanding-text` on `understanding-subtle` | #2a57c9 on #eaf0ff | 5.57 | #6f9bff on #0e1a3a | 6.36 |

The saturated accents are never body text on the light theme: blue on `canvas` is 3.77:1 and red 4.11:1, below AA, so the test also asserts that no allowed pair uses them as a foreground. Body-size blue and red text use the `-text` tints.

**Interactive states.** Hover changes the fill (`surface-hover`) or the border to `fg`; focus is a 2 px `focus` outline with a 2 px offset (`:focus-visible` only), which keeps at least 3:1 against every surface; disabled controls drop to 50 to 60% opacity and are never the only signal (the reason is in text); pressed buttons move down 1 px.

## Elevation and borders

The app is flat. Grouping comes from spacing first, a 1 px `border` hairline second, and a card (a `surface` with a 12 px radius) only when the group is a real object (a session, a balance, a handoff). There are no drop shadows; dialogs and sheets separate from the page with the overlay scrim (`#070707` at 70% in light, black at 80% in dark). Borders never carry meaning alone.

## Motion

Motion is state feedback only (`MOTION_INTENSITY` 2): overlays fade in (200 ms), dialog panels rise 8 px (200 ms), the sheet slides in (240 ms), skeletons pulse, buttons move 1 px when pressed, colors transition in 150 ms. The easing is the deck's `ease-out-quint` (`cubic-bezier(0.22, 1, 0.36, 1)`). Nothing moves at rest, nothing animates on scroll, and under `prefers-reduced-motion: reduce` every animation and transition collapses to 1 ms (the global rule in `src/index.css`). Only `transform` and `opacity` animate.

## Data display rules

- **Money.** `Intl.NumberFormat(locale, {style: 'currency', currency})` over the API's decimal string, never a float, so `9007199254740993.01` stays exact. When the amount has more decimals than the locale shows by default (COP in `es-CO` shows none), the cents the API sent are kept. Amounts render in Geist Mono with tabular figures, right-aligned in tables. The currency is the product's (MXN, COP, ARS, USD), and the format is the viewer's chosen locale.
- **Dates.** `Intl.DateTimeFormat` with `dateStyle: 'medium'` (and `timeStyle: 'short'` for instants) in the viewer's time zone, wrapped in `<time dateTime>`. Relative time (`Intl.RelativeTimeFormat`, numeric auto) only for near events such as session expiry.
- **Masked numbers.** Only the last four characters are ever shown (for example "Terminada en 4821" / "Final 4821" / "Ending in 4821", copy added with the account views in phase 13), in the mono face.
- **Balances.** Every balance shows its as-of instant through `<AsOfNote>` ("Datos al 27 sep 2026, 3:04 p.m."): the data is a snapshot, not a live ledger.
- **Status.** `<StatusPill>` has five states. Only `verified` (an action whose outcome was read back) gets the yellow fill; `pending` is neutral, `failed` and `escalated` are red-tinted, `review_required` is a neutral outline. Each has an icon and a word.
- **Eligibility outcomes** (`indicatively_eligible`, `not_eligible`, `review_required`, `insufficient_data`) never use the yellow verified treatment, a check icon, or wording that suggests approval ("aprobado", "aprovado", "approved" are not used anywhere). They render as neutral text with their reasons, the uncertainty, and the review path, always labeled as an indication from a synthetic service (phase 13).
- **Model-derived content** (an extracted intent, a retrieved passage) is marked with the blue understanding tint and the words that say it came from the model; model output is rendered as plain text, never HTML.

## States

| State | Pattern |
|---|---|
| Loading | `SkeletonGroup` with skeletons shaped like the content, announced once as "Cargando" in a status region; no spinners |
| Empty | `EmptyState`: what is missing, why, and what would fill it |
| Error | `ErrorState` (`role="alert"`): a plain sentence from `errorMessageKey`, the request id for support, and a retry or a way home. Form errors stay inline under their field (`Field.Error`); toasts are for transient confirmations only |
| Partial | The parts that loaded render; the part that failed shows its own inline `ErrorState` with a retry, never a page-wide failure |
| Offline | Failed fetches become `NetworkError` and are retried twice; then the error state says "Sin conexión..." when the browser reports the device offline and "No pudimos conectar con el banco..." otherwise, with a retry |
| Session lost | The app returns to sign-in with the "Tu sesión terminó" notice and, after sign-in, to the same page and conversation |

## Voice and tone

Plain, calm, and precise; serious without being cold. The customer copy is written for Mexico, Colombia, and Argentina (neutral Latin American Spanish with *tú*, never *vos* or *usted* mixed in) and for Brazilian Portuguese (*você*).

- Say what happened and what to do next, in that order: "El código venció. Pide uno nuevo." / "O código expirou. Peça um novo."
- Never blame: "El código no es correcto o los datos no coinciden" rather than "Ingresaste un código incorrecto". One message for a wrong code and an unknown person, so the copy never confirms who is a customer.
- Name the limit and the path: "Desbloqueos y reposiciones pasan a una persona." Escalation is stated as a service, not a failure.
- Never promise approval or imply a decision the system cannot make; eligibility is "indicativa" / "indicativa" / "indicative".
- Numbers and times come from the formatters, never from strings in copy.
- No em or en dashes, no emojis, no exclamation marks, no marketing words. Sentence case for everything, including buttons; button labels are verbs of at most three words ("Enviar código", "Verificar", "Cerrar sesión").
- Tests enforce the mechanical parts: the three locale files share one key set and one set of interpolation variables, and contain no dashes of either kind and no emoji.

## Product surfaces (phase 13)

- **Chat layout.** One column on phones (usable at 360 px) with the composer pinned to the bottom; from 1024 px the glass box sits beside the chat as a panel that scrolls on its own and can be hidden. The customer area widens to 1280 px for this; other customer pages keep their reading width.
- **Messages.** The customer's words sit in a paper bubble on the right; answers are plain text on the canvas with a hairline on the left that turns ink when the answer is selected in the glass box. Structured parts are 12 px cards titled in small semibold text; an escalation is the only red-tinted card. Masked numbers show "Terminada en" in the text face and the four digits in the mono face.
- **Buttons inside answers.** Only the newest answer's options, confirmation, and review buttons act; older ones stay visible and disabled, so the transcript shows what was offered. The card block's confirmation is the `danger` button (it stops the card); the others are ink.
- **Quoted policy.** Clause excerpts the engine appends to a reply move under a "cited policies" disclosure with their `clause_id@version`; an eligibility answer's text moves into a disclosure because its structured view says the same policy sentences plus the rule behind each reason.
- **Eligibility.** A neutral card: the outcome sentence in semibold ink, each reason with its rule, the uncertainty with an info icon, the review path as a secondary button, and the disclaimer in caption text. No yellow, no check icon, no percentage, and no approval wording (tested).
- **Glass box.** A timeline per turn: blue markers for model understanding, yellow for rules, clauses, and verified writes, red for escalations and failed or mismatched writes, gray for reads and versions; each marker's meaning is also written next to the step title. The risk estimate (blue tint) and the eligibility decision (yellow tint) are two panels that never merge, with the note that the language model received neither. The evaluator's internal section is a dashed paper panel labeled "evaluation only". The fixed note that model reasoning is not shown heads every view.
- **Console.** Desktop-first at 1280 px: filters in one row of native selects, then a table sorted by SLA; the SLA is text ("Vence dentro de 2 horas", "Vencido, hace 1 hora") with a clock icon, and overdue adds semibold risk text. Handoff sections are cards in a two-column grid; the credit review repeats the two-panel separation.
- **Evaluation.** Systems are columns (H, B0, B1, P) with their measurement label as a badge under each name; every rate shows its count over the denominator and its 95% interval, zero counts show the one-sided upper bound, and cells under 30 cases carry a "small sample" badge.
