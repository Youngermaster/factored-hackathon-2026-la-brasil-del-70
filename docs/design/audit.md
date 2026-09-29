# Design pre-flight audit (phase 12)

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
