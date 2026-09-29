# Design pre-flight audit (phases 12 and 13)

The `design-taste-frontend` pre-flight checklist (section 14 of the skill) run against the finished foundation: the sign-in screens, the step-up dialog, the preferences sheet, and both layouts, in light and dark themes at 1440 and 390 px wide. Evidence: the screenshots from `apps/web/tooling/screenshots.mjs` (gitignored, `apps/web/.shots/`), the token contrast test, and the vitest-axe tests. Date: 2026-09-29.

The skill targets landing pages; this is product UI, which its section 13 lists as out of scope for the marketing parts. Items about heroes, bento grids, logo walls, marquees, and scroll animation are marked "not applicable" rather than forced.

## Findings and fixes

| Finding | Where | Fix |
|---|---|---|
| `border-strong` (`#8A8A86`) was 2.77:1 on `surface-sunken`, below the 3:1 non-text minimum | Token contrast test, first run | Darkened to `#7A7A77`, one value for both themes (3.44 to 4.68 on every surface) |
| The product name wrapped to two lines and the demo badge overlapped the preferences button at 390 px | Mobile customer screenshots | Wordmark `whitespace-nowrap`; sign-out is icon-only below 640 px, its label kept for assistive technology |
| After sign-in, moving focus to `main` scrolled the page title under the sticky header | Mobile customer screenshot | Focus with `preventScroll` after scrolling to the top; `scroll-padding-top` on `html` |
| "Modo demostración" appeared twice on sign-in (header and page) | Desktop sign-in screenshot | Removed the page badge; the header badge and the one-line hint remain |
| The whole countdown sentence was in the monospace face | Code step screenshot | Only the time is mono, through `<Trans>` with a `time` component |
| Confirmation toasts were announced assertively (Radix default) | Screenshot run (the live region text) | `type="background"` (polite) for neutral and verified toasts, assertive only for risk |
| Two console navigation landmarks with the same name (row and sidebar) | vitest-axe `landmark-unique` | One `nav` that is a row on narrow screens and a sidebar on wide ones |
| Card headers used `<header>`, which some tools expose as a second banner | Testing Library role query | Card headers are `div`s |
| Unused copy (13 keys) in the locale files | Key usage scan | Removed; `errors.offline` is now used for a device that reports itself offline |
| The session-loss redirect raced the route guard, losing the expiry notice and the way back | Integration test | The auth provider leaves the page with a synchronous navigation, then clears the session; sign-out does the same |

## Checklist

| Item | Result |
|---|---|
| Brief inference declared | Yes: `DESIGN.md`, "Direction" |
| Dial values explicit and reasoned | Yes: 4, 2, and 5 (customer) or 7 (console), from the phase brief |
| Design system chosen honestly | Yes: Radix primitives with our own tokens (ADR 0018); no styled kit overridden |
| Redesign mode | Not applicable: new foundation (phase 01 had a one-line shell) |
| Zero em dashes | Yes: `locales.test.ts` fails on em and en dashes in all copy; components hold no copy (`no-hardcoded-strings.test.ts`) |
| Page theme lock | Yes: one theme per page from `<html data-theme>`; no section inverts |
| Color consistency lock | Yes, by meaning: blue, yellow, and red each have one meaning everywhere; the primary action is ink |
| Shape consistency lock | Yes: 6 px controls, 12 px containers, full round only for status pills and timeline markers |
| Button contrast | Yes: every pair in `contrast.ts`, tested in both themes (ink on white 20.1, ink on paper 16.1, white on red 4.56) |
| CTA wrap at desktop | Yes: labels are one to three words |
| Form contrast (inputs, labels, hints, focus) | Yes: borders 3.4:1 or more, hints 5.4:1 or more, focus 16:1 or more |
| Serif discipline | Not applicable: no serif |
| Premium-consumer palette ban | Not applicable, and the palette is the deck's, not beige and brass |
| Italic descender clearance | Not applicable: no italic display type |
| Hero rules (viewport fit, padding, stack, eyebrows, split header) | Not applicable as heroes; the sign-in title block has a heading, one sentence, and one hint, and fits the first viewport on desktop and mobile |
| Eyebrow count | Zero uppercase micro-labels |
| No duplicate CTA intent | Yes: one "Enviar código", one "Verificar", one "Pedir otro código" per screen |
| Logo wall, bento, marquee, zigzag, section repetition | Not applicable |
| Copy self-audit | Done in es, pt, and en; plain sentences, what happened then what to do; no "aprobado" anywhere |
| Motion motivated | Yes: overlay entry, sheet slide, skeleton pulse, pressed state; nothing at rest |
| Reduced motion | Yes: the global rule collapses animation and transitions; screenshots were taken with `reducedMotion: 'reduce'` |
| Dark mode tested in both modes | Yes: vitest-axe runs in both; screenshots in both |
| Mobile collapse explicit | Yes: persona grid, topic grid, key-value lists, and the console navigation collapse below `sm` or `lg` |
| Viewport stability | Yes: `min-h-dvh`, never `h-screen` |
| Effects with cleanup | Yes: the countdown interval, the media query listener, the session-loss subscription |
| Empty, loading, error states | Yes: `EmptyState`, `SkeletonGroup`, `ErrorState` with request id; the guard and the step-up dialog use them |
| Cards only where they carry hierarchy | Yes: the session and the step-up dialog; topics are a divided list, not cards |
| Icons from one allowed library | Yes: Phosphor regular, re-exported from `shared/ui/icons.ts`; no hand-drawn SVG |
| No AI tells (Inter default, purple, three equal cards, fake names, filler verbs) | Yes: the deck's typefaces; personas are ids and plain descriptions, not invented names |
| Decorative dots | None; the three thesis markers on sign-in are semantic and repeat the text beside them |
| Core Web Vitals plausible | Mostly: no images, fonts `swap`; the main bundle is 666 KB (207 KB gzip) because React DOM, React Router, and TanStack Query load up front. Route-level code splitting arrives with the phase 13 surfaces (BACKLOG) |
| One design system | Yes |

## Known gaps

- axe in jsdom cannot evaluate color contrast; the token test covers every allowed pair, and the screenshots were checked by eye. A browser-based axe run is not part of `make check` (browser end-to-end tests are out of scope, CLAUDE.md section 8).
- Instrument Sans's tabular figures were not verified (the font tables could not be inspected without a WOFF2 decoder); amounts therefore use Geist Mono, which is tabular by construction.
- The Portuguese and English copy has not had a native review (pending action in `docs/PROGRESS.md`).

## Phase 13: pre-flight audit of the product surfaces

The `design-taste-frontend` pre-flight checklist run against the chat, the glass box (panel, sheet, and page), the agent inbox and handoff detail, the credit applications, the evaluation view, the evaluator trace, the demo guide, and the About page, in light and dark themes at 1440 and 390 px. Evidence: `apps/web/tooling/screenshots.mjs` driving one conversation per workflow in es and pt through the real API (`DEMO_MODE=true`, `LLM_PROVIDER=fake`, the seeded compose PostgreSQL), the vitest-axe page tests in both themes, and the token contrast test. Date: 2026-09-29.

### Findings and fixes

| Finding | Where | Fix |
|---|---|---|
| The engine appends each cited clause to the reply, so answers read as a paragraph of policy after one line of answer | Every chat screenshot | Verbatim excerpts move under a "cited policies" disclosure with their `clause_id@version`; every other word stays in place |
| An eligibility answer said its eleven reasons twice (text and card) | Credit chat, es and pt | The text moves into a disclosure; the card carries the same policy sentences (tested against the pack) plus each reason's rule |
| Balances as one large card per product crowded the column | Account chat | One "Saldos" card with a row per product, the as-of instant under each |
| "Terminada en 6930" was entirely in the mono face | Balances | Only the digits are mono |
| The glass box panel's toggle leaked onto phones (a utility class conflict) | Mobile chat | The toggle sits in a wrapper that is hidden below 1024 px |
| New turns opened below older expanded entries, off screen | Glass box panel | The newest entry opens and scrolls into view; the first load keeps the top |
| Inbox rows used the engine's English technical summary as the title | Inbox and handoff detail | Titles are the intent in the console language; the summary is a secondary line |
| An approved payment read "Autorizada" while the answer said "concluída" | Payment status (pt) | Settled transactions read "Aplicada" / "Concluída" / "Completed", as the account policy words them |
| Two tables had unnamed, duplicate scroll regions | Evaluation view (axe `landmark-unique`) | `DataTable` names its region by the caption (a phase 12 bug, with a regression test) |
| Heading levels skipped from the page title to part cards | Chat and trace pages (axe `heading-order`) | A visually hidden level-2 heading for the message log and the turn list; panel headings are level 3 |
| The composer box was taller than two lines | Chat | A compact `Textarea` variant |

### Checklist

| Item | Result |
|---|---|
| Brief inference and dials | Unchanged from phase 12: trust-first banking UI; variance 4, motion 2, density 5 (customer) and 7 (console) |
| Zero em dashes | Yes: `locales.test.ts` over all copy; no copy in components |
| Page theme lock, color consistency, shape consistency | Yes: one theme per page; blue, yellow, and red keep one meaning each, repeated in words; 6 px controls, 12 px cards |
| Button and form contrast | Yes: only token pairs from `contrast.ts`; the danger button (white on red, 4.56) appears only for the card block |
| CTA wrap and duplicate intents | Labels are one to three words; one "Hablar con una persona" per screen; the review button names its path |
| Copy self-audit | Done in es, pt, and en; no approval wording in eligibility, About, or demo copy; the demo messages were driven through the API |
| Motion | State feedback only: the typing indicator pulses, disclosures open without animation, reduced motion collapses everything |
| Empty, loading, error, partial states | Every surface: starters before the first message, skeletons, `ErrorState` with the request id and retry, not-found states for conversations, handoffs, applications, and traces, and the evaluation empty state that says how to publish |
| Cards only where they carry hierarchy | Parts, handoff sections, and scenarios are real objects; the trace is a timeline, filters are a plain row |
| Mobile collapse | Chat usable at 360 px; the glass box becomes a sheet; the console tables scroll horizontally inside a named, focusable region |
| Viewport stability and effects cleanup | `min-h-dvh`; the SLA clock interval and the selection scroll effects clean up |
| Icons | Phosphor regular from `shared/ui/icons.ts` only |
| Core Web Vitals plausible | Every page except sign-in is a lazy route; the largest chunk is 422 KB (133 KB gzip), down from one 666 KB bundle |
| Not applicable | Hero, bento, logo wall, marquee, zigzag, and scroll rules (product UI, not a landing page) |

### Known gaps

- The console is designed for 1280 px and wider; on phones the inbox table scrolls sideways.
- Screen reader passes were not run with a real assistive technology; the checks are vitest-axe in jsdom and keyboard review on screenshots.
- Native Portuguese review of the new copy is pending (pending action 38).
