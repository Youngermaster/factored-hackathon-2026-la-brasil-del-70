# Backlog

Items that are out of scope for the phase that found them. Each row names the reason and the phase that owns it. Remove a row in the same commit that resolves it.

| Item | Reason | Owning phase | Priority |
|---|---|---|---|
| Move the LLM API key variables into the `REQUIRED` set of `check_env_keys.py` when a live provider is selected | They are optional while `LLM_PROVIDER=fake` | 08 | Medium |
| Decide the repository license before submission (license undecided; no LICENSE file yet) | The human has not chosen a license; the README states all rights are reserved until then | 17 | High |
| Add the deferred frontend dependencies (React Router, TanStack Query, Radix UI, i18next, react-hook-form, zod, openapi-typescript, openapi-fetch, one icon set) and choose the accessibility test library | Phase 01 ships only the neutral shell; vitest-axe needs a maintenance decision because its latest stable release is 0.1.0 and the 1.0 line has been a prerelease since 2023 | 12 | High |
| Use a non-superuser owner role for migrations in production PostgreSQL | Development and tests use the image bootstrap role `bank_owner` as the owner, which is a superuser inside the throwaway container | 16 | High |
| Require real authentication for Grafana in any non-local `obs` deployment | The development profile uses local-only anonymous viewer access so Compose needs no admin password | 16 | Medium |
| Decide whether `jsonschema` becomes a runtime dependency and validate persisted handoffs against `contracts/schemas/handoff.v1.json` before storing them | Phase 02b added `jsonschema` as a dev dependency and tests golden and builder documents against the schemas; runtime validation is a workflow engine decision | 09 | Medium |
| Record in `docs/data/data-card.md` whether a credit product's `current_balance` is the amount owed or negative when owed, and use it as the `CreditBalanceConvention` for balance answers | Phase 02b defined `available_credit` over an explicit convention with no default, because the data has not been profiled | 03 | High |
| Profile the sign of `amount` for transfers and adjustments and reclassify them in `accounts.direction_of` if the data encodes direction | Phase 02b leaves them `unclassified` in statement totals | 03 | Medium |
| Profile whether `merchant_name` on transfers holds personal names and mask them in the mapper if so | `PaymentStatusView.payee_display` carries sanitized merchant text without a `Pii` marker (a marker inside `Turn` would break a pinned test) | 03 | Medium |
| Provide `credit_profiles` in the DuckDB read backend of the contract suites and derive `CreditProfile` (tenure, credit product count, total limit when one currency, utilization) in the gold layer | The `Readers` protocol of the suites now includes it | 03 | High |
| Strip `internal_fields` (risk estimates, credit review risk, credit profile facts) from every customer-facing DTO, with a test per DTO | Customers may read their own execution records and handoffs at the repository level | 11 | High |
| Add the agent review methods for credit applications (list for review, move to `under_human_review`, close) and list intakes in the agent inbox | Phase 02b gives agents only `get` of an application a handoff references | 13 | High |
| Add a generator lint that requires `workflow` on in-scope scenarios and checks `expected_workflow_path` against the router's registry | The scenario contract keeps `workflow` optional by design | 14 | Medium |
