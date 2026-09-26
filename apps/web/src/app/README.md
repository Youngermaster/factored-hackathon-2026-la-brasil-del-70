# app

The composition root of the web application: providers (TanStack Query, i18n, theme), the router, and the application shell. Phase 12 adds the providers and routes; today `App.tsx` renders a neutral shell.

## Rules

- May import `pages`, `features` (through their `index.ts`), `entities`, and `shared`.
- Nothing imports `app` except `main.tsx`.
- Holds wiring, not behavior: no data fetching, no business rules, no feature-specific state.

## How to extend

Add a provider by wrapping the tree in `App.tsx` (or a `providers.tsx` next to it), and add a route by mapping a path to a page component.

## How to test

Render the shell with React Testing Library and assert landmarks and routes, as in `App.test.tsx`.
