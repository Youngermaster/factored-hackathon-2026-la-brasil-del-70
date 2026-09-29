# app

The composition root of the web application: the services, the providers, the route tree, and the layouts.

| File                                 | Role                                                                                                                                                                                                 |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `services.ts`                        | Creates the API client, the query client, and the session-loss channel once (`createAppServices`)                                                                                                    |
| `AppProviders.tsx`                   | Theme, locale and formatters, icons, tooltips, toasts, the query client, and the API client                                                                                                          |
| `routes.tsx`                         | The route tree: `AuthProvider` at the root with the route error boundary; `/login`; the customer area (`/`) under `CustomerLayout`; the console (`/console`) under `ConsoleLayout`; a not-found page |
| `App.tsx`                            | Builds the browser router and renders it inside the providers                                                                                                                                        |
| `layouts/`                           | `CustomerLayout` (chat-first, mobile-first), `ConsoleLayout` (desktop-first, with navigation), the preferences sheet, the wordmark, the skip link, and route focus handling                          |
| `PublicHeader.tsx`, `RouteError.tsx` | The sign-in header and the route error boundary                                                                                                                                                      |

## Rules

- May import `pages`, `features` (through their `index.ts`), `entities`, and `shared`.
- Nothing imports `app` except `main.tsx` (and the test helpers in `src/test`).
- Holds wiring, not behavior: no data fetching, no business rules, no feature-specific state. Role guards are the auth feature's `RequireSession`, placed by the layouts.

## How to extend

Add a provider in `AppProviders.tsx`; add a route by mapping a path to a page component in `routes.tsx` under the layout whose role may open it; add a console destination to `NAV` in `layouts/ConsoleLayout.tsx`.

## How to test

`src/test/app.tsx` renders the whole app at a path against MSW. `a11y.test.tsx` runs vitest-axe on both layouts and the sign-in steps in both themes; the auth feature's integration tests cover the guards and redirects.
