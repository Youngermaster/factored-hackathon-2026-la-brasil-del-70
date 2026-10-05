# Frontend features

The product surfaces of phase 13, as self-contained features under `apps/web/src/features/`, composed by route-level pages under `apps/web/src/pages/`. Each feature exposes only its `index.ts`; other code never imports its internals (ESLint boundaries). State rules and the full inventory are in [state.md](state.md); primitives in [components.md](components.md); visual rules in [DESIGN.md](../design/DESIGN.md).

| Feature | Public API | Pages that compose it |
|---|---|---|
| `conversation` | `Conversation.Root`, `.Header`, `.Starters`, `.Messages`, `.HumanButton`, `.Composer`; `useConversation` | `CustomerChatPage` (`/`) |
| `human-service` | `useHumanChannel`, `useSendHumanMessage`, `HumanTimeline` | Customer conversation and agent handoff detail |
| `glass-box` | `GlassBox.Panel`, `GlassBox.SheetTrigger`, `GlassBox.Standalone`, `StaffTrace` | `CustomerChatPage`, `GlassBoxPage` (`/glass-box/:id`), `TraceLookupPage` (`/console/traces/:id`) |
| `agent-inbox` | `HandoffFilters`, `HandoffList`, `HandoffDetail`, `CreditApplicationList`, `CreditApplicationDetail` | `AgentInboxPage`, `HandoffDetailPage`, `CreditApplicationsPage`, `CreditApplicationPage` |
| `eval-report` | `EvaluationReport`, the interval helpers | `EvaluationPage` (`/console/evaluation`) |
| `admin-dashboard` | `AdminDashboard` | `AdminDashboardPage` (`/console/dashboard`) |
| `supervision` | `SupervisionOverview` | `SupervisionPage` (`/console/supervision`) |
| `demo-guide` | `DemoGuide`, `SCENARIOS` | `DemoGuidePage` (`/demo`, demo mode only) |

Linked selection between the chat and the glass box lives in `entities/turn-selection` (`TurnSelectionProvider`, `useTurnSelection`): the page provides it, both features read it, so neither feature depends on the other. Every page is a lazy route (`app/routes.tsx`), so the sign-in screen never downloads the console or the chat.

## Conversation

```mermaid
flowchart TD
    page["CustomerChatPage"] --> sel["TurnSelectionProvider (entities)"]
    sel --> root["Conversation.Root<br/>ConversationContext"]
    root --> header["Conversation.Header<br/>slot: glass box toggle, full record link"]
    root --> starters["Conversation.Starters"]
    root --> messages["Conversation.Messages<br/>role=log, aria-live=polite"]
    root --> human["Conversation.HumanButton"]
    root --> composer["Conversation.Composer<br/>2,000 characters, Enter, Shift+Enter"]
    messages --> customer["CustomerMessage<br/>pending, failed, retry"]
    messages --> assistant["AssistantMessage<br/>LanguageScope + MessageContext"]
    assistant --> parts["parts: Notices, AnswerText, Options, Confirmation,<br/>Balances, Payments, Statement, CardStatus, CreditProducts,<br/>Eligibility, ActionStatuses, Escalation, StepUpRequest, Citations"]
    root -.->|useStepUp| auth["features/auth (step-up dialog)"]
```

- **Contexts.** `ConversationContext` (in `Root`) carries the id, the history, the messages in flight, the local notices, and the actions (`send`, `reply`, `retry`, `stepUpAgain`, `startNew`). `MessageContext` scopes one assistant message for its parts (the message, its turn id, and whether its buttons act). Nothing is passed more than one level as props.
- **Quick replies.** Option, confirmation, review, "talk to a person", and the step-up continuation send words the engine's deterministic parsers read; the words live in `chat.replies` and show as the customer's own message. See the decisions in [phase-13.md](../plans/phase-13.md).
- **Language.** Each answer renders in its own language through `LanguageScope` (copy from that language, `Intl` formats for its locale unless it is the viewer's language).

## Glass box

```mermaid
flowchart TD
    panel["GlassBox.Panel / SheetTrigger / Standalone"] --> customerTrace["CustomerTrace<br/>useCustomerTrace + useCitedExcerpts"]
    staff["StaffTrace"] --> staffTrace["useStaffTrace"]
    customerTrace --> body["TraceBody<br/>none, loading, not found, error, records"]
    staffTrace --> body
    body --> turn["TurnTrace<br/>RecordContext, linked selection"]
    turn --> sections["Understanding (blue), Decisions and Clauses (yellow),<br/>Tools, Credit (two panels), Outcome, Versions"]
    turn --> internal["Internal (staff only, separate region)"]
```

- `RecordContext` scopes one execution record for its sections; the view (`customer` or `staff`) decides what the credit panel and the internal section show. The customer trace has no estimate values by schema; the staff trace adds them in the risk panel and the internal section.
- Clause excerpts come from the same turn's message citations (the conversation history cache); the staff view has no history and shows ids only.

## Agent inbox

```mermaid
flowchart TD
    inbox["AgentInboxPage"] --> filters["HandoffFilters<br/>URL search params"]
    inbox --> list["HandoffList<br/>useHandoffs(filters), local sort, SlaText"]
    detailPage["HandoffDetailPage"] --> detail["HandoffDetail<br/>HandoffContext"]
    detail --> sections["VerifiedFacts, ActionsTaken, PolicyBasis,<br/>OpenQuestions, CreditReviewSection, CardRequestSection"]
    detail --> actions["HandoffActions<br/>claim and resolve dialogs"]
    apps["CreditApplicationsPage / CreditApplicationPage"] --> credit["CreditApplicationList / Detail (read only)"]
```

## Evaluation view and demo guide

```mermaid
flowchart TD
    evalPage["EvaluationPage"] --> report["EvaluationReport<br/>useSummaries"]
    report --> run["Run per run id and dataset"]
    run --> tables["MetricTable per workflow, then the aggregate"]
    run --> breakdowns["Breakdowns: language, dialect, segment"]
    tables --> cells["RateCell: rate, n, Wilson 95% or zero-event bound, small-cell flag"]
    dashboardPage["AdminDashboardPage"] --> dashboard["AdminDashboard<br/>run and system selectors"]
    dashboard --> dashboardViews["KPIs, workflow bars, escalation quality,<br/>system comparison, population slices, provenance"]
    dashboard -.->|reuses| reportData["useSummaries"]
    demoPage["DemoGuidePage"] --> guide["DemoGuide<br/>SCENARIOS (verified messages), CopyMessage"]
```

## Data flow with TanStack Query

```mermaid
sequenceDiagram
    autonumber
    participant C as Composer
    participant R as Conversation.Root
    participant Q as Query cache
    participant A as API
    participant G as Glass box
    C->>R: send(text)
    R->>R: pending turn (optimistic, customer message only)
    R->>A: POST /v1/conversations (first message only)
    A-->>R: conversation id, seeded into the history cache and ?conversation=
    R->>A: POST /v1/conversations/{id}/turns {turn_id, text}
    A-->>R: TurnResponse
    R->>Q: append the turn to the history (setQueryData)
    R->>Q: invalidate the trace key
    Q->>A: GET /v1/conversations/{id}/trace
    A-->>G: the new execution record
    alt step_up_required
        R->>R: useStepUp().requestStepUp()
        R->>A: POST the continuation message
    end
```

| Query key | Hook | Written by |
|---|---|---|
| `['api','conversations',id]` | `useConversationHistory`, `useCitedExcerpts` | `useCreateConversation` (seed), `useSendTurn` (append) |
| `['api','conversations',id,'trace']` | `useCustomerTrace` | invalidated by `useSendTurn` |
| `['api','handoffs','list',filters]` | `useHandoffs` | invalidated by claim and resolve |
| `['api','handoffs',id]` | `useHandoff` | set by claim and resolve |
| `['api','credit-applications', ...]` | `useCreditApplications`, `useCreditApplication` | read only |
| `['api','evaluation','summaries']` | `useSummaries` | read only |
| `['api','evaluation','trace',id]` | `useStaffTrace` | read only |

The administrative dashboard reuses `['api','evaluation','summaries']`; changing its run or system is local UI
state and never starts another request. See [the field and formula catalog](admin-dashboard.md).

## Supervision

The evaluator's supervision view composes three read-only sources, each loading and failing in its own section.
It reuses `useSummaries`, `RateCell`, and `SystemLabel` from `@/features/eval-report` through that feature's
`index.ts`. Field catalog: [supervision.md](supervision.md).

```mermaid
flowchart TD
    page["SupervisionPage<br/>RequireSession evaluator"] --> overview["SupervisionOverview"]
    overview --> inv["useModelInventory<br/>GET /v1/eval/models"]
    overview --> e2e["EndToEnd<br/>useSummaries (shared cache)"]
    overview --> live["LiveOperations<br/>useHealthDetails, 503 body at L4"]
    inv --> who["WhoDecides"]
    inv --> served["ServedModels"]
    inv --> offline["OfflineEvidence<br/>IntervalPlot, metric tables, promotions"]
    inv --> llm["LanguageModel<br/>models, price basis, prompts"]
    live --> grafana["link to /grafana/"]
```

A sign-in, sign-out, or lost session drops every cached record (phase 12 `replaceSession`), so nothing from one identity reaches the next.

## Human service

The customer composer switches from assistant turns to persisted human messages after escalation. The assigned agent replies in the handoff detail. Both use the public `human-service` feature, TanStack Query cursor pages and two-second polling; transport failure leaves the persisted lifecycle intact. Closed threads are readable and disable sending. All lifecycle, reconnect, and quota copy lives in es, pt, and en locales. See [the channel specification](../workflows/human-service.md).
