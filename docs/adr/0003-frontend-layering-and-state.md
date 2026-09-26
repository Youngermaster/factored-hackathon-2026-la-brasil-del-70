# 0003: Frontend layering and state rules

- Status: accepted
- Date: 2026-09-26

## Context

The web app has three demanding surfaces (customer chat, transparency panel, agent inbox) plus an evaluation view, built across several phases. Without rules, React code tends toward prop drilling, feature modules reaching into each other's internals, and ad hoc global state, which makes the features hard to test in isolation and hard to change. The UI must also be safe under a strict CSP and never hold session tokens in script-readable storage.

## Considered options

### Structure

1. **Flat `components/` and `hooks/` folders.**
2. **Layered folders** with downward-only imports: `pages` -> `features` -> `entities` -> `shared`, plus `app` as the composition root, and features reachable only through their `index.ts`.

### State

1. **A global store** (for example Zustand or Redux) for most state.
2. **Server state in TanStack Query**, local UI state in components, feature-scoped shared state in context with `useReducer`, and Zustand only by exception.

### Enforcement

1. **Convention and review only.**
2. **ESLint boundary policies** (eslint-plugin-boundaries) checked in CI, with a test that proves they fire.

## Decision

Layered folders, the TanStack Query based state rules, and ESLint enforcement.

- `eslint.boundaries.js` defines the element types and a default-disallow policy set: `app` may import pages, features, entities, and shared; `pages` may import features, entities, and shared; `features` may import entities, shared, and other features; `entities` may import shared. A final policy rejects any import of a file other than a feature's `index.ts` from outside that feature. `tooling/boundaries.test.ts` lints probe imports against a fixture tree and asserts which ones are rejected.
- A Zustand store is allowed only when state must be shared across features or routes and changes frequently, with a written justification in `docs/frontend/state.md`.
- Lint rules also forbid `any`, `dangerouslySetInnerHTML`, and web storage access, backing the security rules in CLAUDE.md section 6.
- The toolchain is Vite 8, React 19, TypeScript 6 (typescript-eslint does not yet support TypeScript 7), ESLint 9 (jsx-a11y does not yet support ESLint 10), Tailwind CSS v4, Vitest with jsdom, Testing Library, and MSW with unhandled requests treated as errors. pnpm is the package manager, pinned through `packageManager`.

## Consequences

- Features can be built and tested in isolation with MSW, and their internals can change without breaking other code.
- Cross-cutting needs must be expressed as shared primitives or entity pieces rather than by importing another feature's internals, which occasionally means moving code down a layer.
- The boundary policies depend on eslint-plugin-boundaries 7, whose policy API is newer and less documented; the fixture test guards against silent misconfiguration.
- TypeScript and ESLint stay one major behind their latest releases until the plugin ecosystem catches up; revisiting that is a deliberate upgrade task.
