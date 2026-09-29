# features

Self-contained product capabilities, one folder per feature (for example `conversation`, `transparency-panel`, `handoff-inbox`). Each feature owns its API calls, state, and UI, and exposes a deliberate public surface.

## Layout

```text
features/<name>/
├── api/        TanStack Query hooks over the typed client (useApi, unwrap, queryKeys)
├── model/      feature-scoped context, reducers, and pure logic
├── ui/         compound components (for example Conversation.Root, Conversation.Messages)
└── index.ts    the only module other code may import
```

## Rules

- May import `entities`, `shared`, and other features through their `index.ts` only.
- Imported by `pages`, `app`, or other features, always through `index.ts`.
- Compose with `children` and slots instead of growing lists of boolean props; share state through a scoped context, not prop drilling.

## How to extend

Create the folder with the layout above, export the public components and hooks from `index.ts`, and add typed MSW fakes for every endpoint it calls under `src/test/msw/`, built from the fixtures in `src/test/msw/api.ts`. `auth` is the reference: sign-in, the session query, the route guard, step-up, and sign-out.

## How to test

One integration test per feature with MSW handlers typed from the generated API types, plus unit tests for reducers and pure logic. Coverage gate: 70% line coverage across `src/features/**`.
