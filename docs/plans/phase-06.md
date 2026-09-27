# Phase 06 plan: policy pack and deterministic policy kernel

Status: the prompt asks for plan mode. The human delegated plan approval to the orchestrator, which pre-approved a plan that follows the prompt, CLAUDE.md, and the existing contracts. Every open question below is decided by the session under the orchestrator's pre-approval. Written against commit `2e48358`, after phase 05.

## What already exists

| Piece | State before this phase |
|---|---|
| Domain | `Decision`, `RuleResult`, `ClauseRef`, `DecisionKind`, `ParamValue` (int, bool, `Money`, short string, list of strings; no float); `ClauseMetadata`, `PolicyClause`, `ActionRequirement`, `ClauseFamily`; `CreditProduct`, `CreditProfile`, `EligibilityAssessment`, `EligibilityView`, `ReviewReason`, `ServiceRef`; `SessionSnapshot`; `TrustState` with a monotone risk tier |
| Ports | `PolicyRepository` (workflow-aware `get_bound`), `EligibilityPolicy` with `EligibilityRequest`, `CreditProductCatalog` |
| Contract suites | `EligibilityPolicy` (fake only) and `CreditProductCatalog` (memory only) |
| Tools | `ToolSettings` with `DEFAULT_MAX_STATEMENT_DAYS = 92` and `DEFAULT_DISPUTE_SLA = 15 days`; the container serves an empty catalog `catalog-unconfigured`; only `block_card` checks step-up |
| Seed | The seeded application names `MX-PL-STANDARD`, `CO-PL-STANDARD`, `AR-PL-STANDARD`; the seeded case uses a 15-day SLA; the borderline persona band is 640 to 660; data ends at the 2026-06-17 snapshot |

## Policy pack format (`policies/`)

```text
policies/
├── README.md                     format, synthetic disclaimer, how to change a clause, review, versioning
├── pack.yaml                     pack id, label, supported workflows, languages
├── versions.lock.yaml            clause id -> version and content digest (monotonic version check)
├── matrix.yaml                   one row per write action
├── bindings.yaml                 common clauses, then workflow -> state -> auth level and clause ids
├── messages/eligibility.<lang>.yaml   outcome, reason, uncertainty, and review path sentences
├── clauses/<family>/<CLAUSE-ID>.<lang>.md    one file per clause per language (es, pt, en)
└── credit/<PRODUCT-CODE>.yaml    one file per product per jurisdiction, with es, pt, en display text
```

- **Clause file.** YAML front matter validated by `ClauseMetadata` (and, in the pack tests, by `contracts/schemas/policy_clause.v1.json` through `jsonschema`), then a customer-facing body with `{param}` placeholders. Placeholders may name only scalar parameters (integer, string, `Money`) of the same clause, so a rendered body never shows a code list.
- **Parity.** Every clause exists in es, pt, and en with the same id, version, jurisdiction, effective date, params, bound rules, and placeholder set.
- **Versioning.** `versions.lock.yaml` records each clause's version and a digest of its three files. A clause whose content changed must carry a higher version than the lock; `bank-agent policy lock` refuses to rewrite the lock otherwise. A pack test fails when the lock and the files disagree, so version numbers can only grow.
- **Pack version.** `pack-` plus the first 16 hex digits of a SHA-256 over every pack file except `README.md`, in path order. Stored in every `Decision` and assessment.

## Clause families

Jurisdiction-specific clauses exist for MX, CO, and AR wherever the values differ; the rest are `ALL`. Every value is synthetic, plausible, and labeled so; none is a real regulation or any bank's terms.

| Family | Clauses | Key parameters | Bound rules |
|---|---|---|---|
| SCOPE | `SCOPE-ALL-1` supported requests; `SCOPE-ALL-2` unsupported requests | `supported_workflows` | `SCOPE.workflow_supported`, `SCOPE.supported_intent`, `SCOPE.action_allowed_in_state` |
| AUTH | `AUTH-ALL-1` identity per action; `AUTH-ALL-2` a document number never proves identity | `step_up_window_minutes` 5, `elevated_risk_required_level` step_up | `AUTH.session_valid`, `AUTH.required_level`, `AUTH.step_up_valid` |
| PRV | `PRV-ALL-1` disclosure and masking; `PRV-ALL-2` third-party requests | `masked_digits` 4 | `PRV.no_cross_customer_access`, `PRV.no_third_party_disclosure` |
| ACC | `ACC-ALL-1` balances and payments with the as-of statement; `ACC-ALL-2` statement period; `ACC-ALL-3` unsupported account requests | `max_statement_days` 92 | `ACC.product_owned_by_session_customer`, `ACC.as_of_disclosed`, `ACC.statement_period_within_limit` |
| CRD | `CRD-ALL-1` card status; `CRD-ALL-2` protective block, step-up, consequences; `CRD-ALL-3` unblock and replacement go to a human | `handoff_sla_hours` 24 | `CRD.card_owned_by_session_customer`, `CRD.card_active`, `CRD.block_requires_step_up`, `CRD.unblock_requires_human`, `CRD.replacement_requires_human` |
| DSP | `DSP-{MX,CO,AR}-1` window; `-2` resolution SLA; `-3` automatic intake limit; `DSP-ALL-1` eligible statuses; `-2` required information; `-3` reason taxonomy; `-4` duplicates; `-5` ownership | window MX 90, CO 60, AR 30 days; SLA MX 45, CO 15, AR 30 days; limit MXN 10,000, COP 2,000,000, ARS 600,000 | the seven `DSP.*` rules |
| ESC | `ESC-ALL-1` escalation criteria; `ESC-{MX,CO,AR}-2` handoff SLA; `ESC-ALL-3` distress and vulnerability; `ESC-ALL-4` credit review and contested results | `repeat_complaint_threshold` 3 in `repeat_complaint_lookback_days` 180, `clarification_budget` 2, `tool_retry_budget` 2; handoff SLA MX 24, CO 24, AR 48 hours | the `ESC.*` rules |
| INF | `INF-ALL-1` after a dispute case opens; `-2` after a card block; `-3` after an application intake | `review_contact_business_days` 5 | none (informational) |
| CRE | `CRE-ALL-1` indicative disclaimer; `-2` catalog information; `-3` unsupported credit requests; `CRE-{MX,CO,AR}-1` rate disclosure basis (CAT, tasa efectiva anual, CFTEA) | `rate_basis` | `CRE.disclaimer_present`, `CRE.product_in_catalog`, `CRE.offered_in_jurisdiction` |
| ELG | `ELG-ALL-1` required facts and the no-decision statement; `-2` risk estimate rules; `-3` products that need a human assessment; `ELG-{MX,CO,AR}-1.1` credit card and `-1.2` personal loan thresholds | score minimum, payment-to-income maximum, days past due maximum, tenure minimum, acceptable bands, review amount; cut points 2000 and 3500 basis points, margin 100 | the `ELG.*` rules |

The CRE and ELG texts and the eligibility messages contain no approval wording, even negated (lexicon test in es, pt, en).

## Matrix, bindings, catalog

- **`matrix.yaml`.** `create_dispute_case`, `block_card`, `submit_credit_application`: confirmation required, base level `otp_verified`, step-up required (CLAUDE.md section 7: every write requires step-up), allowed states per workflow. `ActionRequirement.allowed_states` becomes a mapping from workflow to states (the model is in no contract schema).
- **`bindings.yaml`.** `common` clauses (SCOPE, AUTH, PRV, ESC-ALL-1, ESC-ALL-3) apply to every state; each workflow lists its states with a required auth level and clause ids, where `{country}` resolves from the verified profile. Canonical state names are fixed here for phase 09 (for example `dispute`: `START`, `LOCATE_TRANSACTION`, `COLLECT_DETAILS`, `CONFIRM_DISPUTE`, `CREATE_CASE`, `OFFER_CARD_BLOCK`, `EXECUTE_BLOCK`, `ANSWER_CASE_STATUS`, `ESCALATE`).
- **Catalog (`policies/credit/`).** Nine products: `{MX,CO,AR}-CC-CLASSIC`, `{MX,CO,AR}-PL-STANDARD` (the seeded codes), `MX-MG-FIXED`, `CO-MG-FIXED`, `AR-MG-UVA`; mortgages are information only (`self_service_eligibility: false`). Catalog version `synthetic-catalog-2026.09.1`.

## Kernel (`bank_agent/policy`)

- `policy/pack.py`: the in-memory `PolicyPack` (clauses by id, language, version; bindings; matrix; messages) and `PackPolicyRepository`, which implements `PolicyRepository` over it.
- `policy/loader/`: pure parsing and validation from a mapping of relative path to text (schema, parity, placeholders, lock, bindings, rule parameters, catalog cross-checks). File reading lives in `adapters/policy/` (`FilesystemPolicyRepository`, `FilesystemCreditCatalog`), so the policy layer stays free of I/O.
- `policy/rules/`: pure functions registered by id and version through a decorator registry; each returns a `RuleResult` with the parameters used and the clause refs of the bound clauses that name it. The minimum set from the prompt plus `SCOPE.action_allowed_in_state`, `ESC.tool_failure_exhausted`, `ESC.verification_mismatch`, and `ELG.self_service_product`.
- `policy/facts.py`: `EvaluationRequest` (workflow, state, optional `ActionRequest`, optional `SessionSnapshot`, optional `TrustState`, `PolicyFacts`). Record facts are optional (missing gives a safe failure); detector signals default to "not detected". `PolicyFacts.data_as_of` is the reference date for every time window.
- `policy/evaluator.py`: the rules to run are the bound rules of the clauses bound to the workflow state, in the registry order (AUTH, PRV, SCOPE, ACC, CRD, DSP, CRE, ESC); ELG rules run only in the eligibility service. Precedence: an AUTH failure (deny before step-up), then refuse, escalate, deny, step-up from other rules, abstain, clarify; with every rule passed, an action needing confirmation without `confirmed_at` gives `require_confirmation`, otherwise `allow`.
- `policy/explain.py`: renders clause bodies with their params in the session language (locale-formatted money) and returns the text and `clause_id@version` citations. No language model.
- `policy/eligibility/`: `SyntheticEligibilityService` and its renderer.

## Synthetic eligibility service

- Parameters come from the ELG clause for the product's jurisdiction and type, never from the product's own clause list.
- Outcome mapping, first match wins: a product without self-service eligibility gives `review_required` (`product_requires_human_assessment`) and no other rule runs; any missing fact gives `insufficient_data`; an unavailable or `unknown` estimate, a borderline interval, days past due above the maximum, or an amount above the review threshold gives `review_required`; any other failed rule gives `not_eligible`; only a clean pass gives `indicatively_eligible`.
- Income is the profile's estimated income, else the customer's declared income. The monthly payment of a loan is the annuity at the product's maximum rate over the requested term; for a card it is a clause percentage of the requested limit.
- The renderer turns an `EligibilityView` into es, pt, or en text: outcome, each reason with its citation, the uncertainty statement, the review path, and the `CRE-ALL-1` disclaimer. It raises if approval wording appears.

## Tool parameters and time windows

- `ToolSettings` loses the two defaults: `max_statement_days` comes from `ACC-ALL-2`, the dispute SLA per country from `DSP-{country}-2`, and `step_up_actions` from the matrix; the create-dispute and credit-application tools check step-up like `block_card`.
- `PolicySettings` (`POLICY_DIR`, `POLICY_DATA_AS_OF`, default 2026-06-17, the organizer snapshot date). The container exposes the pack, the kernel with its data as-of date, the eligibility service, and the filesystem catalog. Windows never read the wall clock.
- The seed takes the seeded case's SLA from the pack; the borderline band stays 640 to 660 because the AR personal loan minimum is 650.

## Files to create or change

`policies/**`; `services/api/src/bank_agent/policy/**`; `adapters/policy/**`; `domain/policy.py` (`ActionRequirement`); `application/tools/{context,writes}.py`; `bootstrap/{settings,container,persistence}.py`; `cli.py` (`policy lock`, `policy catalog`); `Makefile`; `.env.example`; `data_platform/src/bank_data/seed/{bundle,command,criteria}.py`; docs listed below.

## Tests to add

- Unit: one module per rule family with boundary values and missing-fact safe failures; evaluator precedence; loader validation on small temporary packs; renderer formatting; eligibility mapping.
- Property (Hypothesis): the six invariants of the prompt.
- Integration (they read the repository pack): schema of every front matter, parity, placeholders, lock, bindings name clauses, catalog validation, lexicon, renderer golden texts in es and pt, and the YAML situation table (normal, unsupported, and escalation rows per workflow and jurisdiction family).
- Contract: `SyntheticEligibilityService` in the `EligibilityPolicy` suite and `FilesystemCreditCatalog` in the catalog suite (the suite becomes adapter-agnostic about product counts and codes).

## Docs

`policies/README.md`, `docs/policy/catalog.md` (generated), `docs/policy/eligibility.md`, `docs/workflows/policy-evaluation.md`, ADR 0011, the policy package README, indexes, PROGRESS, BACKLOG.

## Risks

- Clause volume (about 40 ids in three languages) is large; files are small and committed family by family.
- State names are fixed before phase 09 builds the machines; they are data, and the bindings test catches drift.
- Step-up on every write adds one code entry to the dispute and credit demos.
- Bilingual quality needs human review; recorded as a pending action, not a blocker.

## Open questions, each decided by the session under the orchestrator's pre-approval

1. Step-up for dispute and application writes: required, following CLAUDE.md section 7; the tools enforce the matrix too (defense in depth).
2. Where the loader reads files: an adapter; the policy layer parses text only.
3. Which rules run: the bound rules of the bound clauses, so rules and explanations come from the same files.
4. Effect precedence: as above; escalation dominates denial and automatic resolution, authentication failures dominate everything.
5. Eligibility precedence: the prompt's order read as first match wins (safer: uncertainty goes to a human).
6. Data as-of: a setting with the snapshot date as default, passed as a fact.
7. Version monotonicity: a committed lock file with digests plus a lock command.
8. Credit score near the threshold is not a separate review reason (the contracts have none); the AR personal loan minimum 650 keeps the persona band.
9. Pack content tests are integration tests because they read the repository; rule tests are unit tests over small packs.
