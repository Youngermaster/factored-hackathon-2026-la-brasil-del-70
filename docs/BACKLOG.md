# Backlog

Items that are out of scope for the phase that found them. Each row names the reason and the phase that owns it. Remove a row in the same commit that resolves it.

| Item | Reason | Owning phase | Priority |
|---|---|---|---|
| Move the LLM API key variables into the `REQUIRED` set of `check_env_keys.py` when a live provider is selected | They are optional while `LLM_PROVIDER=fake` | 08 | Medium |
| Decide the repository license before submission (license undecided; no LICENSE file yet) | The human has not chosen a license; the README states all rights are reserved until then | 17 | High |
| Add the deferred frontend dependencies (React Router, TanStack Query, Radix UI, i18next, react-hook-form, zod, openapi-typescript, openapi-fetch, one icon set) and choose the accessibility test library | Phase 01 ships only the neutral shell; vitest-axe needs a maintenance decision because its latest stable release is 0.1.0 and the 1.0 line has been a prerelease since 2023 | 12 | High |
| Use a non-superuser owner role for migrations in production PostgreSQL | Development and tests use the image bootstrap role `bank_owner` as the owner, which is a superuser inside the throwaway container | 16 | High |
| Require real authentication for Grafana in any non-local `obs` deployment | The development profile uses local-only anonymous viewer access so Compose needs no admin password | 16 | Medium |
| Add a JSON Schema validator (for example `jsonschema`, MIT) as a dependency and validate persisted handoffs against `contracts/schemas/handoff.v1.json`, with a test that validates builder documents against every committed schema | Phase 02 added no dependency; the schemas are generated from the models that already validate every document | 09 | Medium |
