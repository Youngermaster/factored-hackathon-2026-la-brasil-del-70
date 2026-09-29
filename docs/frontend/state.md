# Frontend state inventory

Where every piece of state in `apps/web` lives, under the rules in CLAUDE.md section 6 and [ADR 0003](../adr/0003-frontend-layering-and-state.md): server state in TanStack Query, local UI state in components, feature-scoped shared state in context with `useReducer`, and Zustand only with a written justification here.

**Zustand: not used.** No state is both shared across features or routes and changing frequently. The session is server state; the theme, locale, toasts, and step-up requests are small contexts that change on user action.

## Server state (TanStack Query)

| Key (`queryKeys`) | Source | Stale time | Owner | Notes |
|---|---|---|---|---|
| `['api', 'auth', 'session']` | `GET /v1/auth/me` | 0 (always refetched on mount and window focus) | `features/auth` (`useSession`) | `null` when signed out (a 401 is mapped to `null`, not an error). Route guards and the session status read it. Replaced in place on sign-in, step-up, sign-out, and session loss (`replaceSession`), which also drops every other cached record so nothing from one identity reaches the next |
| `['api', 'conversations', id]` | `GET /v1/conversations/{id}` | 30 s default | `features/conversation` (`useConversationHistory`), read by `features/glass-box` for clause excerpts | Seeded empty by `useCreateConversation`; each turn is appended with `setQueryData` from the turn response, so the chat never refetches what it just received |
| `['api', 'conversations', id, 'trace']` | `GET /v1/conversations/{id}/trace` | 30 s default | `features/glass-box` (`useCustomerTrace`) | Invalidated by every sent turn |
| `['api', 'handoffs', 'list', filters]` | `GET /v1/agent/handoffs` | 30 s default | `features/agent-inbox` (`useHandoffs`) | One entry per filter set; the due window becomes `sla_due_before` when the request is made. Invalidated by claim and resolve |
| `['api', 'handoffs', id]` | `GET /v1/agent/handoffs/{id}` | 30 s default | `features/agent-inbox` (`useHandoff`) | Replaced by the claim and resolve responses |
| `['api', 'credit-applications', ...]` | `GET /v1/agent/credit-applications[/{id}]` | 30 s default | `features/agent-inbox` | Read only |
| `['api', 'evaluation', 'summaries']`, `['api', 'evaluation', 'trace', id]` | `GET /v1/eval/summaries`, `GET /v1/eval/conversations/{id}/trace` | 30 s default | `features/eval-report`, `features/glass-box` (`useStaffTrace`, no retry) | Read only |

Defaults (`createQueryClient`): `staleTime` 30 s, refetch on window focus, retries only for network errors and 5xx (at most two), never for a 4xx; mutations never retry automatically.

Mutations (no cache of their own): sign-in start and verify, step-up start and verify, sign-out (`features/auth/api/session.ts`); create a conversation and send a turn (`features/conversation/api/conversation.ts`); claim and resolve a handoff (`features/agent-inbox/api/handoffs.ts`).

## Context (app-wide, provided by the composition root)

| Context | Value | Changes when | Persisted |
|---|---|---|---|
| `ThemeContext` (`useTheme`) | preference (system, light, dark) and the resolved theme | The person picks a theme, or the system theme changes | `localStorage` display preference (`shared/lib/preferences.ts`) |
| `LocaleContext` (`useLocale`, `useFormat`) | locale (`es-MX`, `es-CO`, `es-AR`, `pt-BR`, `en-US`), language, `Intl` formatters | The person picks a language and region | `localStorage` display preference |
| i18next instance (`useTranslation`) | Copy for the language | With the locale | No |
| `ApiContext` (`useApi`) | The typed client and the in-memory CSRF token store | Never replaced | The CSRF token is memory only; the session is an `HttpOnly` cookie the script never sees |
| `ToastContext` (`useToast`) | `notify()` and the list of open toasts | A toast opens or closes | No |
| Phosphor `IconContext`, Radix `TooltipProvider` | Icon defaults, tooltip delay | Never | No |

## Context (feature-scoped)

| Context | Feature | Value |
|---|---|---|
| `StepUpRequestContext` (`useStepUp`) | auth | `requestStepUp()`; the pending resolver lives in a ref inside `AuthProvider`, the open flag in its state |
| `StepUpDialogContext` | auth | The challenge, the verify call, failures, restart, and cancel for the parts of one step-up dialog |
| `FieldContext` (`useField`) | shared/ui | The ids and validity of one form field |
| `ConversationContext` (`useConversation`) | conversation | The conversation id, history, messages in flight, local notices, the draft, the composer ref, and the actions (`send`, `reply`, `retry`, `stepUpAgain`, `startNew`); provided by `Conversation.Root` |
| `MessageContext` (`useMessage`) | conversation | One assistant message for its part renderers, its turn id, and whether its buttons act (only the latest answer, only when nothing is in flight) |
| `TurnSelectionContext` (`useTurnSelection`) | entities/turn-selection | The selected turn and where the selection came from; provided by the chat page, read by the chat and the glass box (linked selection) |
| `RecordContext` (`useRecord`) | glass-box | One execution record, the view (customer or staff), and its cited excerpts, for the trace sections |
| `HandoffContext` (`useHandoffView`) | agent-inbox | The handoff the detail sections and the claim and resolve actions render |
| `LanguageScope` (nested `LocaleContext` and i18next instance) | shared/i18n | Another language for one subtree: an assistant answer in Portuguese renders in Portuguese, formatted for `pt-BR`, whatever the chrome language |

## Local component state

| Component | State | Why local |
|---|---|---|
| `LoginFlow` | `useReducer`: identify or code step, the open challenge, the identification (for resend), failed attempts | One screen's flow; nothing else reads it |
| `CodeEntry` | The typed code, the "incomplete" flag, the countdown (`useSecondsUntil`) | One form |
| `DocumentForm` | react-hook-form with a zod/mini schema | One form |
| `OneTimeCodeInput` | Focus, for the active digit box | Presentation only |
| `useTableSort` | The sort key and direction of one table | One table |
| `Conversation.Root` | `useReducer` (`chatReducer`): the customer's messages still in flight or failed (optimistic rendering applies to them only) and client notices (a cancelled step-up); the composer draft | The chat's own flow; settled turns live in the query cache |
| `CustomerChatPage` | Whether the glass box panel is open on wide screens | Presentation only |
| `TurnTrace` | Whether one trace entry is expanded (the newest opens by default; selecting its message opens it) | Presentation only |
| `ClaimDialog`, `ResolveDialog` | Open state, the chosen outcome, the note | One dialog each |
| `CopyMessage` | Whether the example was copied | One button |

## URL state

- `/login?next=<path>` keeps where a signed-out visitor was going; `/login?reason=expired&next=<path>` after a lost session; `/login?reason=signed-out` after sign-out. `next` is validated by `safeNextPath` (same-app paths only).
- `/?conversation=<id>` keeps the open conversation across reloads and re-authentication without web storage; the chat writes it when the first message creates the conversation and reads it to resume.
- `/console/inbox?status=&workflow=&priority=&reason=&language=&due=` holds the inbox filters (shareable, and the back button works); unknown values are ignored, never sent.
- `/console/traces/<conversation id>` is the evaluator's lookup; `/glass-box/<conversation id>` is the customer's full-width glass box.

## What is never stored

Session tokens, CSRF tokens, one-time codes, and customer data never go to `localStorage`, `sessionStorage`, or IndexedDB. ESLint bans web storage everywhere except `shared/lib/preferences.ts` (and tests).
