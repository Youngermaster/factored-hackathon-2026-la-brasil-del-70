# Phase 13: Product surfaces (chat, glass box, agent inbox, evaluation view)

Not a plan-mode phase. The human delegated approvals, so every open question below is decided by the session by the most defensible option, with the reasoning next to it. The pull at the start was a fast-forward no-op ("Already up to date"); local `main` already holds the merge of `origin/main` (pending action 37).

Scope (orchestrator brief): the four workflows end to end in the web app, with Spanish and Portuguese customer copy and English and Spanish console copy (the locale files keep one key set, so the console also has Portuguese text): the customer chat, the glass box, the agent inbox with credit review items, the evaluation view, the About page, and a demo guide for judges and the pitch video. ADR 0025's scope (assistant preferences, a mock human agent, Langfuse) is not built: the human decided the build does not follow it, and the API has no assistant profile route, so the chat header shows no assistant name or avatar.

## Design read

Reading this as: trust-first banking product UI (a customer chat usable at 360 px, a glass box beside it, agent and evaluator consoles at 1280 px and wider), in the phase 12 identity (DESIGN.md): calm, precise, color only for meaning. Dials unchanged: `DESIGN_VARIANCE` 4, `MOTION_INTENSITY` 2, `VISUAL_DENSITY` 5 (customer) and 7 (console).

## Routes

| Path | Role | Page | Loading |
|---|---|---|---|
| `/login` | anyone | `LoginPage` (links to the demo guide in demo mode, and to About) | eager |
| `/about` | anyone | `AboutPage` (es, pt, en) | lazy |
| `/demo` | anyone, only when `VITE_DEMO_MODE=true` (else not found) | `DemoGuidePage` | lazy |
| `/` | customer | `CustomerChatPage` (`?conversation=<id>` resumes) | lazy |
| `/glass-box/:conversationId` | customer | `GlassBoxPage` (full-width trace for the video) | lazy |
| `/console` | agent, evaluator | `ConsoleOverviewPage` | lazy |
| `/console/inbox`, `/console/inbox/:handoffId` | agent | `AgentInboxPage`, `HandoffDetailPage` | lazy |
| `/console/credit-applications`, `/console/credit-applications/:applicationId` | agent | `CreditApplicationsPage`, `CreditApplicationPage` | lazy |
| `/console/evaluation` | evaluator | `EvaluationPage` | lazy |
| `/console/traces`, `/console/traces/:conversationId` | evaluator | `TraceLookupPage` (the evaluator glass box, with the internal section) | lazy |

## Features (`apps/web/src/features/`)

| Feature | Public API (`index.ts`) | Inside |
|---|---|---|
| `conversation` | `Conversation.Root`, `.Header`, `.Messages`, `.Composer`, `.HumanButton`, `.Starters`; `useConversation` | `api/` (create, send turn, history hooks), `model/` (reducer of optimistic and settled turns, quick replies, part language), `ui/parts/` (one renderer per `AssistantMessage` part) |
| `glass-box` | `GlassBox.Panel`, `GlassBox.Sheet`, `GlassBox.Standalone`, `StaffTrace` (evaluator view) | `api/` (customer and evaluator trace hooks), `model/` (trace to entries: state path, rules, clauses, tools, versions, timing; the auth-check marker), `ui/` sections |
| `agent-inbox` | `HandoffList`, `HandoffFilters`, `HandoffDetail`, `CreditApplicationList`, `CreditApplicationDetail` | `api/` (list, get, claim, resolve; credit applications), `model/` (filters in the URL, SLA text, sorting), `ui/` |
| `eval-report` | `EvaluationReport` | `api/` (summaries), `model/` (Wilson intervals, zero-event bound, small cells, system labels), `ui/` tables |
| `demo-guide` | `DemoGuide` | The scenario catalog (personas, workflows, paths, es and pt example messages), copy buttons |

Linked selection lives in `entities/turn-selection` (`TurnSelectionProvider`, `useTurnSelection`): the page provides it, and both features read it, so neither feature owns the other. Pages compose these with no business logic; `app/routes.tsx` uses React Router `lazy` routes.

## Decisions on open questions

| Question | Decision | Why |
|---|---|---|
| Clarification options carry option ids, but `SendTurnRequest` has only `text` | Each option button keeps its `option_id` (key and `data-option-id`) and sends the ordinal the engine parses deterministically ("Opción 2", "Opção 2"), shown as the customer's message | No API change; `parse_choice` reads ordinals in es and pt; the transcript shows exactly what was chosen |
| Confirmation card buttons | Confirm sends "Sí, confirmo" / "Sim, confirmo"; Cancel sends "No, cancelar" / "Não, cancelar" | `parse_yes_no` reads both; the customer sees the words sent |
| "Talk to a person" (BACKLOG, phase 13) | A persistent button in the composer bar sends "Quiero hablar con una persona" / "Quero falar com uma pessoa". The gate's deterministic signal (`signals:keyword@1`) sets `human_requested` on every turn, and the kernel escalates at START (`ESC.human_requested`) in any state, so no engine change is needed. Disabled while a turn is in flight and after the conversation is escalated or closed | The row asks for "a plain yes (or a button)": the button closes it. A plain "sí" after an abstention needs the engine to remember the offer; that narrower item moves to phase 14, where the evaluation set can show whether customers answer that way |
| Eligibility review path button | Labeled by `review_path`; sends "Sí, quiero que una persona lo revise" / "Sim, quero que uma pessoa revise", a yes the EXPLAIN state takes as accepting its offer (intake confirmation, review handoff with `credit_review`, or a contact handoff) | The generic "hablar con una persona" wording would be escalated by the gate before the credit handler and lose the `credit_review` section |
| Step-up | A turn with `step_up_required` opens the phase 12 dialog through `useStepUp()`; on success the chat sends "Listo, ya confirmé mi identidad" / "Pronto, já confirmei minha identidade", which resumes the pending write (the API contract); on cancel a notice says nothing was done and offers the step-up again | Documented continuation in `docs/api/README.md` |
| Interactive parts on old messages | Only the latest assistant message's options, confirmation, and review buttons are enabled, and only when no turn is in flight | An old button would answer a question the engine no longer asks |
| Language of part labels and formats | Part labels use the message's `language` (`i18n.getFixedT`); money and dates use the viewer's locale when its language matches the message, else `pt-BR` for pt and `es-MX` for es | A Portuguese conversation reads in Portuguese whatever the chrome language |
| Conversation id and resume | Created on the first send; the id goes into `?conversation=` (replace), so reloads and re-authentication resume through `GET /v1/conversations/{id}`; a 404 shows a notice and starts fresh | Phase 12 already carries the id through re-authentication without web storage |
| Glass box placement | Desktop (1024 px and wider): a collapsible panel beside the chat (collapse state is local); mobile: a Sheet from a "Registro" button; `/glass-box/:conversationId` renders it full-width for the video | The prompt's panel, sheet, and separate route |
| Clause excerpts in the trace | The trace has clause ids only; excerpts come from the same turn's message citations, in the session language; a clause without a citation shows its id and version | No second source of clause text in the browser |
| Evaluator trace | Evaluators open `/console/traces/:conversationId` (id pasted or typed); the internal section (risk estimate values, risk tier, trust events, safety interventions) sits in its own labeled region below the customer-visible sections. Agents have no trace (the API answers 403) | Evaluators read every trace but no history (phase 11) |
| Auth-check decisions (BACKLOG, phase 13) | A decision with `AUTH.*` rules whose other rules all report missing facts is labeled "state access check" and collapsed by default | Phase 09a records it like any decision; the label prevents misreading missing facts as failures |
| Credit review items (BACKLOG, phase 13) | A read-only credit applications list and detail next to the handoffs. The backend widens agent visibility to every reviewable intake (`submitted`, `under_human_review`) plus any a handoff references, as phase 02b decided (a submitted intake is a review item of its own). Status transitions stay out (the prompt makes the list read only) | ADR 0021; `docs/plans/phase-02b.md` question 1 |
| `list_my_credit_applications` (BACKLOG, phase 13) | Built: a read tool, `ToolName` value, every contract to 1.3.0, and the credit status path without an application id | The `cre-co-application` demo persona asks for status without an id |
| Assessment and conversation on intakes (BACKLOG, phase 13) | Built with the same contract release | The agent's credit application view shows both links |
| Catalog display names (BACKLOG, phase 13) | Built: `display_name` on each credit product part, in the message language | Product cards name the product instead of only its code |
| Evaluation summary shape | Additive (schema 1.1.0): `measurement` may be `offline`, `simulated`, or `projected`; `breakdowns` (language, dialect, segment, optionally per workflow); `automation_attempted` and `cost_per_resolution_usd` on every metrics block; `failure_table` (a repository path) | The prompt asks for the attempted share, both cost figures, breakdowns, and the three labels; nothing is published yet (BACKLOG, phase 14), so the change breaks no file |
| Confidence intervals | Computed in the browser from the published counts: Wilson 95% for proportions, the exact one-sided 95% upper bound `1 - 0.05^(1/n)` for zero events; cells under 30 cases are flagged small | Deterministic from the numbers shown; labeled with the method |
| System labels | `human`/`h` is H, `baseline_b0`/`b0` is B0, `baseline_b1`/`b1` is B1, `proposed`/`p` is P; any other id is shown as published | The harness names systems in phase 14 |
| Filters and sorting in the inbox | Filters live in the URL search params (shareable, back button) and go to the API; sorting (priority, SLA due, created) is local | The API filters; sorting a bounded page locally is enough |
| SLA countdown | Text first ("Vence en 3 h", "Venció hace 20 min") with a clock icon; overdue adds the word and the risk text color | WCAG 1.4.1 |
| Demo guide visibility | Public route shown only when `VITE_DEMO_MODE=true`, linked from the sign-in page's demo hint | The personas are demo labels already shown in demo mode |
| Zustand | Not used | No state is shared across routes and changing often; linked selection is a page-level context |
| Bundle | Route-level `lazy` for every page except sign-in; the build must not warn above 500 KB per chunk | BACKLOG row, phase 13 |

## Backend changes (small, each with tests on memory and PostgreSQL)

| Change | Files |
|---|---|
| Agents list and read every reviewable credit intake | A migration after `0009` (row-level security policy for the agent role), `CreditApplicationRepository.list_for_review` and `get` in both adapters, contract suite, RLS tests, `docs/security/data-isolation.md` |
| `list_my_credit_applications` read tool and the status path without an id | `ToolName`, the tool port and adapters, the guarded toolset, `policies/matrix.yaml` and the credit state bindings, the credit status handler and templates (es, pt, en goldens), every contract to 1.3.0 (`make contracts`, `contracts/README.md` changelog) |
| Intake links | `submit_credit_application` records the assessment id and the originating conversation |
| Product display names | `display_name` on credit product parts, from the catalog's es, pt, and en names |
| Evaluation summary 1.1.0 | `bank_agent.domain.evaluation`, the API schema, the filesystem adapter tests |
| OpenAPI | `make openapi` regenerates `contracts/openapi.json` and `apps/web/src/shared/api/generated/schema.d.ts` |

## Tests to add (Vitest, React Testing Library, MSW typed from `schema.d.ts`)

- Conversation: normal path through confirmation, verified action, and case reference; clarification option click; step-up flow; failed action never shown as success; escalation notice; character limit; network error with retry; Portuguese rendering and formatting; balances with the as-of date; a two-currency statement never summed; a card block through step-up; every eligibility outcome without success styling or approval wording, with the review path; resume from `?conversation=`; the talk-to-a-person button.
- Glass box: rules, clauses, tools, and verification for a turn; linked selection both ways; the reasoning note; a credit turn with separate risk estimate and eligibility panels; the customer view without estimate values; a workflow switch marker; the auth-check label.
- Agent inbox: every filter and sorting; the detail view with every section, including `credit_review` and `card_request`; claim and resolve with confirmation; credit applications list and detail.
- Evaluation view: per-workflow and aggregate tables, intervals, "not defined", small cells, the three measurement labels, breakdowns, the empty state.
- Demo guide and About: render, copy buttons, demo-mode gating.
- Accessibility: vitest-axe on every page in both themes.

Web feature coverage stays at 70% or more (`src/features/**`).

## Docs

- `docs/frontend/features.md` (new): a Mermaid composition diagram per feature, context boundaries, and TanStack Query data flow.
- `docs/frontend/state.md`, `docs/frontend/components.md`, `docs/design/DESIGN.md` (chat and glass box rules), `docs/design/audit.md` (the pre-flight audit per surface).
- `docs/demo/script.md` (new): the demo script outline for the pitch video.
- `docs/api/README.md`, `docs/workflows/credit-information.md`, `docs/security/data-isolation.md`, `contracts/README.md`, `apps/web/README.md`, `docs/BACKLOG.md`, `docs/PROGRESS.md`.

## Risks

- **Size.** Four surfaces plus a demo guide. Mitigation: one feature at a time, each committed with its tests; the backend changes run in a separate worktree and are cherry-picked.
- **Demo messages that do not work on seeded data.** Every example in the demo guide is driven through the real API (Playwright, `LLM_PROVIDER=fake`) before it is listed; an example that fails is fixed or left out, never listed untested.
- **Keyword-driven quick replies.** The buttons send text the deterministic parsers read; a parser change would break them. Mitigation: the phrases live in the locale files and the backend scenario tests cover the same phrases.
- **Bundle size.** Radix and TanStack Query stay in the entry chunk; the pages split.

## Verification

- `pnpm --dir apps/web run test:coverage`, `lint`, `typecheck`, `build` (chunk sizes).
- The API with `DEMO_MODE=true` and `LLM_PROVIDER=fake` on the seeded compose PostgreSQL and the Vite dev server; `tooling/screenshots.mjs` drives one conversation per workflow in es and pt through the real API and screenshots the chat, glass box, inbox, evaluation view, and demo guide in light and dark at 1440 and 390 px (gitignored `apps/web/.shots/`).
- `make check` in the background, polled.

## Open questions

None block correctness. The native Portuguese review of the new copy joins pending action 38.
