# shared

Foundation code with no knowledge of the product domain: UI primitives built on Radix, the typed API client, i18n setup, and small libraries. Phase 12 fills it.

## Planned layout

```text
shared/
├── ui/              accessible primitives (Button, Dialog, Field) styled with design tokens
├── api/             openapi-fetch client with credentials: 'include', CSRF header, problem-details parsing
│   └── generated/   types generated from the backend OpenAPI (make openapi); never edited by hand
├── i18n/            i18next setup and locale files (es, pt, en)
└── lib/             framework-free helpers
```

## Rules

- Imports nothing from `app`, `pages`, `features`, or `entities`.
- Imported by every other layer.
- No `any`; generated types are the source of truth for API shapes.

## How to extend

Add a primitive under `ui/` with keyboard support, visible focus, and a test; add a helper under `lib/` with a unit test.

## How to test

Unit and render tests with Vitest and React Testing Library; vitest-axe checks for primitives (phase 12).
