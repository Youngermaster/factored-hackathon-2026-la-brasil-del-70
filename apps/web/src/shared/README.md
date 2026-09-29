# shared

Foundation code with no knowledge of the product domain: UI primitives built on Radix, the typed API client, i18n setup, and small libraries.

## Layout

```text
shared/
├── ui/              accessible primitives on Radix, tokens.css, contrast.ts, the theme, icons (docs/frontend/components.md)
├── api/             openapi-fetch client (credentials, request id, CSRF, problem details), query client and keys
│   └── generated/   schema.d.ts, generated from contracts/openapi.json by make openapi (openapi-typescript); never edited by hand
├── i18n/            i18next setup, locale files (es, pt, en), Intl formatters, the locale switcher
├── config/          build-time switches (VITE_DEMO_MODE)
└── lib/             framework-free helpers (cx, display preferences, safe redirect paths)
```

## Rules

- Imports nothing from `app`, `pages`, `features`, or `entities`.
- Imported by every other layer.
- No `any`; generated types are the source of truth for API shapes.

## How to extend

Add a primitive under `ui/` with keyboard support, visible focus, and a test; add a helper under `lib/` with a unit test.

## How to test

Unit and render tests with Vitest and React Testing Library beside each module, vitest-axe checks for the overlays and display primitives, the token contrast test (`ui/tokens.test.ts`), and the locale file tests (`i18n/locales.test.ts`).
