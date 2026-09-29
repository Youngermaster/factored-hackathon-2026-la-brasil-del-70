# Frontend state inventory

Where every piece of state in `apps/web` lives, under the rules in CLAUDE.md section 6 and [ADR 0003](../adr/0003-frontend-layering-and-state.md): server state in TanStack Query, local UI state in components, feature-scoped shared state in context with `useReducer`, and Zustand only with a written justification here.

**Zustand: not used.** No state is both shared across features or routes and changing frequently. The session is server state; the theme, locale, toasts, and step-up requests are small contexts that change on user action.

## Server state (TanStack Query)

| Key (`queryKeys`) | Source | Stale time | Owner | Notes |
|---|---|---|---|---|
| `['api', 'auth', 'session']` | `GET /v1/auth/me` | 0 (always refetched on mount and window focus) | `features/auth` (`useSession`) | `null` when signed out (a 401 is mapped to `null`, not an error). Route guards and the session status read it. Replaced in place on sign-in, step-up, sign-out, and session loss (`replaceSession`), which also drops every other cached record so nothing from one identity reaches the next |
| `['api', 'conversations', ...]`, `['api', 'handoffs', ...]`, `['api', 'credit-applications', ...]`, `['api', 'evaluation', ...]` | Phase 13 | 30 s default | Phase 13 features | Declared in the key factory now so invalidation is planned in one place |

Defaults (`createQueryClient`): `staleTime` 30 s, refetch on window focus, retries only for network errors and 5xx (at most two), never for a 4xx; mutations never retry automatically.

Mutations (no cache of their own): sign-in start and verify, step-up start and verify, sign-out (`features/auth/api/session.ts`).

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

## Local component state

| Component | State | Why local |
|---|---|---|
| `LoginFlow` | `useReducer`: identify or code step, the open challenge, the identification (for resend), failed attempts | One screen's flow; nothing else reads it |
| `CodeEntry` | The typed code, the "incomplete" flag, the countdown (`useSecondsUntil`) | One form |
| `DocumentForm` | react-hook-form with a zod/mini schema | One form |
| `OneTimeCodeInput` | Focus, for the active digit box | Presentation only |
| `useTableSort` | The sort key and direction of one table | One table |

## URL state

- `/login?next=<path>` keeps where a signed-out visitor was going; `/login?reason=expired&next=<path>` after a lost session; `/login?reason=signed-out` after sign-out. `next` is validated by `safeNextPath` (same-app paths only).
- `/?conversation=<id>` keeps the open conversation across re-authentication without web storage; phase 13's chat reads it.

## What is never stored

Session tokens, CSRF tokens, one-time codes, and customer data never go to `localStorage`, `sessionStorage`, or IndexedDB. ESLint bans web storage everywhere except `shared/lib/preferences.ts` (and tests).
