# Phase 12: Frontend foundation and design system

The prompt asks for plan mode and a human-approved design direction. The human delegated approval to the orchestrator and asked for autonomous execution; the orchestrator pre-approved the design direction recorded below. Every open question is decided in this plan by the most defensible option and marked "decided by the session under the orchestrator's pre-approval".

The pull at the start failed: local `main` and `origin/main` have diverged (10 local commits, phases 10b and 11, not pushed; 20 on origin: PRs 7, 8, 12, 15, 16, 17). `git pull --ff-only` refuses, and the protocol forbids merging or rebasing over others' work without the human, so the phase runs on local `main` as the orchestrator instructed. The human reconciles the branches (a merge) before pushing.

## Design read

Reading this as: a trust-first banking product UI (customer chat on mobile and desktop, agent and evaluator consoles on desktop), with a calm, precise language, leaning toward Radix primitives, Tailwind v4 tokens, and the team pitch deck's own identity so the demo and the video read as one product.

Dials (from the prompt): `DESIGN_VARIANCE` 4, `MOTION_INTENSITY` 2, `VISUAL_DENSITY` 5 for the customer surfaces and 7 for the consoles.

## Pre-approved design direction (orchestrator)

The app shares one visual identity with the pitch deck in `slides/` (`slides/styles/tokens.css`, `slides/lib/scene/kit.ts`, `slides/lib/scene/contrast.ts`):

- **Palette "Azure Skies":** ink `#070707`, blue `#3772FF`, red `#E12B37`, yellow `#FDC840`, light gray (paper) `#E6E6E4`, with the deck's tints (`#6F9BFF`, `#F0616A`) and deep fills (`#0E1A3A`, `#2B2208`, `#2E0B0E`) in the dark theme.
- **Color semantics, never swapped:** blue is the language model and understanding; yellow is deterministic decisions and verified actions; red is risk, refusal, and escalation; light gray is data and paper.
- **Type:** the deck's three families, self-hosted through `@fontsource-variable` (no CDN, so the strict CSP holds): Instrument Sans (UI and body), Unbounded (display, used sparingly: the wordmark and page titles), Geist Mono (amounts, codes, identifiers).
- **Banking restraint:** a calm light theme by default for customer screens (light gray and white surfaces, ink text, one accent at a time); an optional dark theme close to the deck's ink ground; accents reserved for meaning (a verified action gets yellow, an escalation red, model-derived understanding blue), never decoration; WCAG 2.2 AA contrast verified by a test (ink text on yellow; no small red or blue text below AA); generous spacing; no gradients; no emojis; one outline icon set; no em dashes in UI copy.

## Decisions on open questions

All decided by the session under the orchestrator's pre-approval.

| Question | Decision | Why |
|---|---|---|
| Icon set | Phosphor (`@phosphor-icons/react`), `regular` weight only, through a `shared/ui/icon` re-export | Outline style; preferred by both taste skills (minimalist-ui bans Lucide); MIT; one family |
| Accessibility test library | `vitest-axe` 0.1.0 with `axe-core` pinned as a direct dev dependency (4.13) and our own `vitest` type augmentation | CLAUDE.md names vitest-axe; 0.1.0 is a thin wrapper whose `axe-core` range resolves to the maintained release; the 1.0 line is still a prerelease. jsdom has no layout, so axe's color-contrast rule is incomplete there; contrast is covered by the token contrast test instead |
| Radix packaging | The `radix-ui` umbrella package (tree-shaken per primitive) | One version for every primitive; MIT; 105 KB unpacked |
| Router | `react-router` 8 in data mode (`createBrowserRouter`), `createMemoryRouter` in tests | CLAUDE.md names React Router; route error boundaries come built in |
| Theme persistence without a flash | `public/theme-init.js`, a classic external script in `<head>` (CSP `script-src 'self'` compatible), reads the stored preference and sets `data-theme` before first paint; CSS falls back to `prefers-color-scheme` when nothing is stored | No inline script; no flash |
| Where preferences live | `localStorage` key `bank-agent.preferences.v1` (theme and locale only), through one module `shared/lib/preferences.ts`; the ESLint web-storage ban stays for every other file and gets a documented, file-scoped exception for this module only | The ban exists for session data; a theme is a per-viewer convenience; reads and writes are wrapped in try/catch |
| Demo mode in the SPA | `VITE_DEMO_MODE=true` shows the persona picker, labeled as demo mode; the persona catalog is a static list in the auth feature (ids from `docs/demo/personas.md`, descriptions in the locale files). The demo code is shown only when the challenge says `delivery_channel: "demo"` | The API has no endpoint that lists personas or reports demo mode, and persona ids are demo labels, not secrets. Document login is always available |
| UI language and formatting locale | One locale switcher with five options: `es-MX`, `es-CO`, `es-AR`, `pt-BR`, `en-US`. The language (`es`, `pt`, `en`) is the prefix; `Intl` uses the full tag. Default from `navigator.languages`, else `es-MX` | One control, and money and dates follow the country the customer picks |
| Money | `Intl.NumberFormat(locale, {style: 'currency', currency})` over the decimal string from the API (never parsed to a float), rendered in Geist Mono with tabular figures | Exact decimals; aligned columns |
| 401 handling and resume | The API client reports a 401 on any request except the auth calls that may legitimately answer 401 (`/v1/auth/verify`, `/v1/auth/step-up/verify`); the auth provider clears the session cache and navigates to `/login?reason=expired&next=<path and search>`. `next` keeps the conversation id (`?conversation=<id>`); only same-app paths are accepted (no open redirect) | Keeps the conversation id without web storage |
| CSRF | An in-memory token store: bootstrapped with `GET /v1/auth/csrf` before the first unsafe request, replaced from every login, step-up, and logout response, and refreshed once, with one retry, on `403 csrf-token-invalid` | Matches ADR 0031 |
| Query retries and stale times | Retry at most twice on network errors and 5xx, never on 4xx; `staleTime` 30 s by default, 0 for the session (`/v1/auth/me` is the source of truth for guards), `refetchOnWindowFocus` on | Documented in `apps/web/README.md` |
| Hard-coded string rule | A Vitest tooling test (`tooling/no-hardcoded-strings.test.ts`) walks every `.tsx` under `src/` with the TypeScript compiler API and fails on JSX text with letters and on literal `aria-label`, `title`, `placeholder`, `alt`, and `label` values | No new dependency; runs in `make check` |
| Zustand | Not used. Session is server state (TanStack Query); theme, locale, toasts, and step-up are small contexts | Nothing is shared across routes and changing frequently |
| BACKLOG: `/v1` dev proxy | Done in this phase | Owned by 12 |
| BACKLOG: clear the session cookie on a 401 | Done: the problem handler deletes the session cookie on `authentication-required` and `session-expired` when the request carried one. `Clear-Site-Data` on logout is rejected: `"cookies"` would also drop the new anonymous CSRF cookie the same response sets, and `"storage"` would erase the viewer's theme and locale | Small API change with tests |
| BACKLOG: accept the "talk to a person" offer with a yes or a button | Moved to phase 13 | It needs the chat surface (phase 13) and an engine change; phase 12 has no conversation UI |
| ADR number | ADR 0018 (the prompt's number; it is free locally and on origin) | |
| Visual verification | `playwright-chromium` as a web dev dependency; `tooling/screenshots.mjs` drives the login flow against the running API and dev server and writes to `apps/web/.shots/` (gitignored) | The prompt asks for screenshots; not part of `make check` (CLAUDE.md puts browser end-to-end tests out of scope) |

## Files to create or change

| Area | Files |
|---|---|
| Tokens and theme | `src/shared/ui/tokens.css` (light and dark tokens, mapped into `@theme`), `src/shared/ui/contrast.ts` (the allowed text pairs and WCAG math), `src/shared/ui/theme/` (provider, `useTheme`, switcher), `public/theme-init.js`, `src/index.css` (fonts, base) |
| Primitives (`src/shared/ui/`) | Button, IconButton, Link; Field (Label, Control, Hint, Error), Input, Textarea, Select, OneTimeCodeInput; Dialog, Sheet, Tabs, Tooltip, Toast; Card (Header, Body, Footer), Badge, StatusPill; AsOfNote; Stack, Inline; Skeleton, EmptyState, ErrorState; KeyValueList; DataTable (compound, sortable headers, caption); Timeline; JsonView; each with a colocated test |
| Shared lib | `src/shared/lib/` (`cn`, preferences, safe `next` paths, request ids) |
| i18n | `src/shared/i18n/` (i18next setup, provider, locale switcher, `Intl` formatters), `src/shared/i18n/locales/{es,pt,en}.json` |
| API layer | `src/shared/api/` (openapi-fetch client with CSRF, request id, and problem middleware; `ApiError` and problem parsing; CSRF store; query client; query key factory; `ApiProvider`) |
| Auth feature | `src/features/auth/` (`api/` hooks, `model/` personas, session context, step-up context, `ui/` persona picker, document form, code entry, expired notice, step-up dialog, session status, logout button, route guard, `index.ts`) |
| App shell | `src/app/` (providers, router, `CustomerLayout`, `ConsoleLayout`, not-found page, route error boundary); `src/pages/` (login, customer home, console overview, not found) |
| Tooling | `tooling/no-hardcoded-strings.test.ts`, `tooling/screenshots.mjs`, `vite.config.ts` (`/v1` proxy, Vitest pool and timeouts), `eslint.config.js` (preferences exception), `index.html` |
| Backend | `services/api/src/bank_agent/api/problems.py` or its caller: clear the session cookie on the two session 401s, with tests |
| Docs | `docs/design/DESIGN.md`, `docs/design/audit.md`, `docs/frontend/components.md`, `docs/frontend/state.md`, `apps/web/README.md`, layer READMEs, ADR 0018 and the index, `docs/api/README.md` (cookie clearing), BACKLOG, PROGRESS |

## Tests to add

- **Unit:** every primitive (roles, keyboard, focus trap and return in Dialog and Sheet, Tabs arrow keys, OneTimeCodeInput paste and backspace, DataTable sort state and `aria-sort`, JsonView renders markup as text); formatters for `es-MX`, `es-CO`, `es-AR`, `pt-BR`, `en-US`; problem parsing; the query key factory; retry policy; CSRF store; `next` path validation; theme provider and `theme-init.js`; token contrast for every declared pair in both themes; locale files (same keys in all three, no em dash, no emoji).
- **Integration (MSW, typed from `schema.d.ts`):** persona login, the code, then the right layout per role (customer, agent, evaluator); document login; a wrong code and the lockout message; a 401 mid-session leading to re-authentication and back to the same conversation id; the CSRF header on every unsafe request; step-up from a feature; logout.
- **Accessibility:** vitest-axe on the login screen (persona step and code step), the expired notice, the step-up dialog, and both layouts, in light and dark.
- **Coverage:** the 70% line gate for `src/features/**` stays; the session adds no exclusion.

## Vitest under load

`make check` runs Vitest after the Python suites, often while the machine is busy. The config pins `pool: 'forks'`, caps workers, and raises the test, hook, and teardown timeouts so a slow worker start is not a failure; no test is skipped and no gate changes.

## Risks

- Scope: about 25 primitives plus the shell, API layer, auth, i18n, tests, and docs. Mitigation: each primitive stays small and composes Radix; the conversation, glass box, inbox, and evaluation features stay in phase 13.
- axe in jsdom cannot judge color contrast; the token contrast test covers it and the screenshots are checked by eye.
- React Router 8 and Radix under React 19.3 and TypeScript 6: check peer ranges on install.
- The diverged `main`: the human must merge before pushing; this phase touches mostly `apps/web/` and docs, so conflicts are expected only in `docs/PROGRESS.md`, `docs/BACKLOG.md`, and `docs/adr/README.md`.
