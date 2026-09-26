# pages

Route-level components. A page composes features and entities for one route and passes route parameters down. It holds no business logic and no data fetching of its own.

## Rules

- May import `features` (only through their `index.ts`), `entities`, and `shared`.
- Imported only by `app` (the router).
- No prop drilling beyond two levels; use a feature-scoped context or a query hook instead.

## How to extend

Add `src/pages/<route-name>/` (or a single file) exporting the page component, then register it in the router in `app`.

## How to test

Integration tests render the page with MSW handlers for its features and assert what the user sees, including loading, empty, and error states, plus a vitest-axe check on key screens (phase 12).
