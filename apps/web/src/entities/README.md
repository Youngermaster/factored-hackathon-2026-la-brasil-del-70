# entities

Domain types and small presentational pieces shared by several features: for example a `Money` display that formats with `Intl` per locale, a case status badge, or a transaction row. Entities know nothing about API calls, routes, or feature state.

## Rules

- May import `shared` only.
- Imported by `features`, `pages`, and `app`.
- Types derive from the generated API types in `shared/api/generated/` where they represent server data.

## How to extend

Add `src/entities/<entity>/` with its types, formatters, and presentational components, exported from an `index.ts`.

## How to test

Unit tests for formatters (money, dates, and numbers per `es-MX`, `es-CO`, `es-AR`, `pt-BR`) and render tests for presentational components.
