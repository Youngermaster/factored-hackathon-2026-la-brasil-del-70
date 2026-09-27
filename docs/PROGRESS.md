# Progress

Continuity for the build lives in this file, not in chat history. Every phase adds an entry to the phase log and updates the current state.

## Current state

| Field | Value |
|---|---|
| Last completed phase | 05, core banking, identity, and customer isolation: PostgreSQL schema with forced RLS, adapters passing every shared suite, the mock identity service and sessions, banking tools with read-back verification, the demo seed |
| Next phase | 06, policy pack and kernel (`kit/prompts/06-policy.md`). It must also publish the synthetic credit catalog (with the product codes the seed uses) and replace the tool defaults phase 05 left (statement cap, dispute SLA); see `docs/BACKLOG.md` |
| Blocked | None |

Pending human actions (none blocks phase 06):

0. **Review the phase 02 and phase 02b domain model and contracts before phases 05, 06, and 09 start.** The summaries are in the phase 02b and phase 02 entries below; contracts change cheaply now and expensively later.

1. **License undecided; decide before submission.** No LICENSE file exists and the README says all rights are reserved until the team chooses. Tracked in `docs/BACKLOG.md` for phase 17.
2. **Check the organizer data-use terms before the repository is made public.** `data_platform/sample/` holds 2,595 pseudonymized organizer rows under CLAUDE.md rule 5; the terms are not in the repository. Tracked for phase 17. Optionally add `BANK_DATA_SOURCE=s3` to your `.env` (see `.env.example`) so `make pipeline` uses the full data by default.
3. `.claude/settings.json` still allows `npm ci`, `npm install *`, and `npm run *`, and asks for `npx *`. Sessions did not change permission settings. If you want pnpm commands pre-approved, add equivalents such as `Bash(pnpm install *)`, `Bash(pnpm run *)`, `Bash(pnpm --dir apps/web *)`, and `Bash(pnpm exec *)`, and consider `Bash(pnpm dlx *)` under `ask`.
4. Run `/status` in Claude Code from the repository root and record the loaded setting sources in the phase 00 entry below.
5. **Choose the language model provider** (phase 08 left it undecided). Until then `LLM_PROVIDER=fake` refuses every model call and workflows will run on their deterministic fallbacks.
6. **Record real cassettes once the provider and key are chosen.** Every cassette in `evals/cassettes/` is a hand-authored fixture (`provenance: hand_authored_fixture`, model `fixture/hand-authored`); `evals/cassettes/README.md` has the recording steps. This is not a blocker.
7. **Verify the price table.** `services/api/config/llm_prices.yaml` lists candidate prices (Anthropic `claude-sonnet-5` 2.00/10.00 and `claude-haiku-4-5-20251001` 1.00/5.00, OpenAI `gpt-5-mini` 0.25/2.00, USD per million tokens) with `verified: false`. Open each `source_url`, correct the numbers and date, and set `verified: true`; until then the budget guard charges 1.5 times the listed price.
8. **Review the optional `litellm` extra before enabling it.** litellm 1.102.1 (MIT) is 84 MB alone and 170 MB with its dependencies, above the 50 MB rule, and it handles provider API keys. It is pinned exactly, lazily imported, and never installed by `make setup`; check its advisories before `uv sync --extra litellm`.
9. **Review the data platform dependency footprint.** DuckDB, dbt-duckdb, and Pandera are named in the CLAUDE.md stack and boto3 in the phase prompt, so they were added without asking; together with their dependencies (dbt-core, pandas, numpy, botocore, agate) the development environment grew by about 340 MB. Individually the largest are the DuckDB binary (44 MB), pandas (41 MB), and botocore (25 MB). The API image needs only DuckDB (for the gold readers).
10. **Review the workflow prioritization** (`docs/decisions/workflow-prioritization.md`): confirm the build and depth order (`account_inquiry`, `card_support`, `dispute`, `credit`), read the "Breadth risk" section (`credit` is the weakest candidate for depth; `card_support` has no demand evidence under the strict mapping; `dispute` has the weakest data support), and decide whether the pre-registered weights stand. A weight change is a new pre-registration version (`docs/analysis/workflow-scoring-preregistration.md`); rerun `make analysis DATA_SOURCE=s3`.
11. **Start the automatable-share labeling task** (`docs/analysis/labeling-protocol.md`). The 600-item sample is at `data/labeling/automatable_sample.csv` (gitignored; regenerate with `make analysis DATA_SOURCE=s3`); two labelers per item, adjudicated, without opening `automatable_prelabels.csv` first. 75 items per workflow is the floor. Expect `card_support`, `dispute`, and `credit` items to be labeled as not matching their workflow: transcripts are two balance templates. This does not block any phase; the scores use the labeled proxy until then.
12. **Verify or replace the cost assumptions** in `data_platform/analysis/cost_assumptions.yaml` (loaded cost per handled minute: MX 0.18, CO 0.14, AR 0.16 USD; after-call work 1.15; all `assumption: true`, `verified: false`) before any cost figure leaves the repository as more than an illustration.
13. **Review the matplotlib footprint.** matplotlib 3.11.2 with pillow, fonttools, kiwisolver, contourpy, cycler, and pyparsing adds about 54 MB to the development environment (matplotlib 24 MB, fontTools 14 MB, PIL 13 MB), at the 50 MB guideline. It was added without asking because the phase prompt names it; it is a `bank-data` dependency only and never enters the API image.
14. **Decide whether `docs/adr/0000-team-alignment-and-hackathon-strategy.md` belongs in the ADR index.** It was merged from the team repository during phase 05 (only its whitespace was changed so `make docs-check` passes). It is not listed in `docs/adr/README.md`, and parts of it (for example a ten-day deadline and a feature lock on day 1) are team statements the phase log does not record elsewhere.
15. **Review the phase 05 security design before phase 11 exposes it**: `docs/security/identity-and-sessions.md`, `docs/security/data-isolation.md`, and ADRs 0008 to 0010. Identity lookups and one-time codes derive their keys from `SESSION_SECRET`, so rotating it requires `make seed` again.

## Phase log

### Phase 05: mock core banking, identity, and customer isolation (2026-09-27)

Plan: `docs/plans/phase-05.md`. The prompt asks for plan mode; the human delegated plan approval to the orchestrator, which pre-approved a plan that follows the prompt, CLAUDE.md, and the phase 02 and 02b contracts. Every open question was decided by the session under that pre-approval and is recorded in the plan.

#### What was done

| Commit | Change |
|---|---|
| `0c62291` | The plan: schema, row-level security design, session design, decided open questions |
| `fe722ae` | Alembic 1.20.0 |
| `4c05c69` | Seven Alembic revisions: context helpers and the identity directory; products, transactions, complaints, credit profiles; dispute cases, credit applications, the action ledger table; sessions, one-time-code challenges, trust events; conversations, turns, execution records, handoffs, audit events; forced RLS; least-privilege grants, append-only triggers, the `eval` schema and `bank_evaluator` role |
| `8a981a9`, `48f9e3d` | PostgreSQL unit of work, repositories, mappers, session store, standalone audit log, seeder; revision 0008 (audit replay check); `PostgresBackend` in both contract backend lists; one migrated testcontainers database per test session |
| `5d029df`, `52e5ad9` | Integration tests for RLS, agent and evaluator limits, append-only tables, the credit status constraint, the evaluation schema |
| `67faac0` | `MockIdentityProvider`, `IdentityKeys`, `DemoOtpSender`, the challenge store, `OtpPolicy` and `SessionPolicy` |
| `e848899` | `SessionService` (login, step-up with rotation, resolution, logout, revocation), `PostgresChallengeStore`, identity integration tests |
| `14f1161` | `ActionLedger` port (memory and PostgreSQL, contract suite), `ToolArgumentError` |
| `47f32b8` | tzdata 2026.4 |
| `a512409`, `b6494d9` | Banking tools (`SessionContext`, read and write tools, engine-only credit profile read, audit with redacted arguments), `WriteVerifier`, `ToolFailureInjector`; tool contract suites on memory and PostgreSQL; mapper round-trip and tool rule unit tests |
| `9ef2238` | `bootstrap/persistence.py` and container wiring; `bank-agent db upgrade` |
| `f12e7b3` | `bank-data seed`, `data_platform/seed/personas.yaml`, `make seed`, `make db-upgrade`; bank-data depends on bank-agent |
| `4dd6700`, `6ada48d`, `d1ed01c`, `6de9a4c`, `9718bc8` | Adapters and application READMEs, `docs/security/identity-and-sessions.md`, `docs/security/data-isolation.md`, `docs/demo/personas.md`, ADRs 0008 to 0010, data platform README |
| `3184ab1` | Whitespace fix in `docs/adr/0000-team-alignment-and-hackathon-strategy.md` (merged from the team repository during the phase) so `make docs-check` passes |
| This commit | BACKLOG and this entry |

#### Review summary

- **Schema.** Reference tables (`customers`, `products`, `transactions`, `historical_complaints`, `credit_profiles`, `identity_directory`, `staff_members`) are read only for the application role, except `UPDATE (status, status_changed_at)` on products. Written aggregates store their validated domain document as JSONB next to the scalar columns used by queries and policies, with check constraints tying them together. Composite foreign keys keep every transaction, case, and turn on its own customer's records. Idempotency keys are unique per customer.
- **Row-level security.** Enabled and forced on every table. Policies read `app.role` and `app.customer_id`, which the unit of work sets with `set_config(..., true)` as its first statement; without a context every policy is false. Agents read every handoff and only the cases and applications a handoff references; evaluators read records, audit events, and handoffs; the `identity` role serves sessions and challenges; the `seed` policies apply to the owner role only. Details: `docs/security/data-isolation.md`.
- **Concurrency.** Writes take `FOR NO KEY UPDATE NOWAIT` locks; a row held by another open unit of work marks the unit of work conflicted and `commit` raises `ConcurrencyConflictError`, matching the memory adapter without blocking requests.
- **Identity.** Persona id or document plus phone last four; unknown identifications get an indistinguishable challenge and the same error. Codes: six digits, HMAC-SHA256 with a per-challenge salt and a key derived from `SESSION_SECRET`, constant-time comparison, 5 minutes, 5 attempts, 15-minute lockout. Sessions: 256-bit token stored as a SHA-256 digest, 15-minute idle and 60-minute absolute expiry, rotation on step-up (5-minute window), logout and revocation. Details: `docs/security/identity-and-sessions.md`.
- **Tools.** Reads for all four workflows, scoped by the session (another customer's id is not found); balances always carry `as_of`; statements total per currency and cap the period at 92 days until phase 06; the credit catalog is filtered by the verified jurisdiction. Writes: `create_dispute_case`, `block_card` (step-up required), `submit_credit_application` (status `submitted`, never a decision); all idempotent by key. No unblock or replacement tool. `get_my_credit_profile` lives on engine-only tools. Every call writes an audit event with redacted arguments in its own unit of work.
- **Seed.** 16 customer personas and 2 staff personas selected by named criteria and a seeded hash; every workflow's normal, ambiguous, and escalation paths have a persona; two synthesized records (one open case, one application intake), labeled `seed`. Only keyed digests of document numbers and phone digits are stored.

#### Decisions

- [ADR 0008](adr/0008-server-side-opaque-sessions.md): server-side opaque sessions instead of JWT.
- [ADR 0009](adr/0009-row-level-security-as-defense-in-depth.md): row-level security as defense in depth behind tool-layer scoping.
- [ADR 0010](adr/0010-idempotency-keys-and-read-back-verification.md): idempotency keys and read-back verification for writes.
- `AccessContext` stays the database context; the application adds `SessionContext` (session plus instant) for tools.
- Identity keys derive from `SESSION_SECRET` with HMAC and fixed labels; no new environment variable.
- Lifetimes are constants in code (`application/identity/policy.py`), not settings.
- The container uses the PostgreSQL adapters when the application role is configured and empty memory adapters otherwise; the identity service needs `SESSION_SECRET`; the credit catalog is empty (`catalog-unconfigured`) until phase 06.
- Dependencies (pinned in `uv.lock`): alembic 1.20.0 (MIT) with mako 1.4.3 (MIT), named in the CLAUDE.md stack; tzdata 2026.4 (Apache-2.0) for customer-local dates in slim images. Both are a few MB. bank-data gained a workspace dependency on bank-agent (lockfile change only).

Deviations from the prompt and plan, found during implementation:

- Revision 0008 was added: PostgreSQL applies SELECT policies to an explicit `ON CONFLICT` arbiter, so audit replays from contexts that cannot read audit events use a narrow `SECURITY DEFINER` digest lookup.
- `block_card` idempotency needed a new port, `ActionLedger` (`action_idempotency` table), added to the unit of work with memory and PostgreSQL adapters and a contract suite.
- `trust_events` was added to the schema because the `SessionStore` port stores trust state; it is append-only like the audit tables.
- SQL is written with bound `text()` statements instead of SQLAlchemy table metadata, so there is no `tables.py` to drift from the migrations; the migrations are the only schema definition.
- `get_product_status` returns a `ProductStatusView` (status and expiry, no balances or internal fields) for cards and other products alike.
- The similar-transfer criterion accepts amounts within 5%, because equal amounts are rare in the data.
- Tool suites live under `tests/contracts/` so they run on both the memory and the PostgreSQL backends.

#### How to verify

```bash
make check                                                     # needs Docker; never reads .env
make up && make seed                                           # compose PostgreSQL; full gold when BANK_DATA_SOURCE=s3
make seed                                                      # again: same counts, no changes
uv run pytest services/api/tests/contracts -q -k postgres      # PostgreSQL adapters in every shared suite
uv run pytest services/api/tests/integration/test_row_level_security.py services/api/tests/integration/test_schema_guards.py -q
uv run pytest services/api/tests/integration/test_identity_postgres.py data_platform/tests/integration/test_seed.py -q
uv run bank-agent db upgrade                                   # schema at revision 0008
```

Results recorded in this phase:

| Check | Result |
|---|---|
| `make check` | Exit 0 |
| Python tests | 1,387 unit and 208 integration tests pass (1,326 and 63 before); the PostgreSQL adapters run every shared contract suite |
| Coverage gates | All 11 pass: application 95.4%, adapters 98.0%, bootstrap 100%, domain 99.7%, ports 100%, `data_platform/src` 96.7% |
| Import contracts | 5 kept |
| Docs check | markdownlint 0 issues; 27 mermaid blocks in 94 files parse |
| Guards | No emoji; attribution clean; gitleaks found no leaks |
| `make seed` (full delivery, `BANK_DATA_SOURCE=s3`) | 200 customers, 559 products, 6,119 transactions, 84 complaints, 200 credit profiles, 200 identity entries, 2 staff, 1 seeded case, 1 seeded application; selection in about 1 second; a second run leaves the same counts; schema at revision 0008 |

#### Known limitations

- The development and test owner is the image superuser, which bypasses RLS; the seed policies and the audit replay check are written for a non-superuser owner that phase 16 must introduce and verify.
- RLS protects rows, not columns: internal fields (fraud labels, days past due, credit profile facts) must still be stripped from customer-facing DTOs and model inputs (BACKLOG, phases 09 and 11).
- No HTTP routes, cookies, or CSRF yet (phase 11); `DemoOtpSender` is the only code delivery.
- The credit catalog is empty until phase 06; the seeded application names `CO-PL-STANDARD`, which phase 06 must publish. The statement cap (92 days) and dispute SLA (15 days) are defaults until phase 06 policy parameters exist.
- Seeded data ends at the 2026-06-17 snapshot; time-based policy windows must use the data's as-of instant (BACKLOG, phase 06).
- Portuguese paths are played by Mexican, Colombian, and Argentine personas: the data has no Brazilian customers.
- Nothing purges expired sessions and challenges yet (BACKLOG, phase 15).

#### Next phase

Phase 06, policy pack and kernel (`kit/prompts/06-policy.md`): the synthetic clauses in the prioritization order, the `ELG` eligibility parameters, the synthetic credit catalog (including the product codes the seed uses), and the tool parameters that phase 05 left as defaults.

### Phase 04: demand evidence and workflow prioritization (2026-09-26)

Plan: `docs/plans/phase-04.md` (no plan mode, per the orchestrator; the human pre-approved plans and had already confirmed the four-workflow scope, so the phase continued after the prioritization document instead of stopping for confirmation). Data: the full organizer delivery (`BANK_DATA_SOURCE=s3`), recorded in every report header.

#### What was done

| Commit | Change |
|---|---|
| `17cafb9` | The plan, from profiling the phase 03 warehouse |
| `0f3b5f8` | The pre-registration (`docs/analysis/workflow-scoring-preregistration.md`, `data_platform/analysis/scoring.yaml`) and the reason mapping with three scenarios, committed before any score was computed |
| `4458f61` | matplotlib for the figures |
| `2d71a25` | `bank_data.analysis` (mapping, metrics, seeded bootstrap, kappa, Cramer's V, spikes, scoring and sensitivity, labeling export and pre-labels, figures, reports), `bank-data analysis`, `make analysis`, the cost assumptions, unit tests, the mapping coverage test, and the fixture integration test |
| This commit | Generated reports and figures, the labeling protocol, the analysis README, the prioritization decision, ADR 0023, the data card, data platform README, docs index, BACKLOG, and this entry |

#### Headline results (primary mapping, pre-registered weights)

| Rank | Workflow | Score | Contacts (share) | First contact resolution | Handle time | CSAT 1 or 2 | Automatable, proxy | Data support | Cost per resolved contact (projected) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `account_inquiry` | 70.4 | 240,056 (31.9%) | 91.5% | 221 s | 20.8% | 70.1% | 92% | 0.76 USD |
| 2 | `card_support` | 64.4 | 150,863 (20.0%) | 89.6% | 266 s | 22.2% | 68.6% | 98% | 0.93 USD |
| 3 | `dispute` | 63.5 | 144,154 (19.1%; 27,133 complaints) | 43.6% | 435 s | 54.5% | 33.2% | 32% | 3.13 USD |
| 4 | `credit` | 55.8 | 54,879 (7.3%) | 65.2% | 540 s | 39.1% | 50.0% | 70% | 2.60 USD |

- Sensitivity: first and last place hold in all 12 weight variants; `card_support` and `dispute` (0.9 points apart, a pre-registered tie broken by data support) swap in 1 of 12 (data support weight minus 5). Strict mapping: `card_support` and `credit` have no unambiguous interaction demand. Alternative mapping (`Producto` to `credit`): `credit` second, `card_support` last.
- Sub-intents: all 11 non-escalation sub-intents are classed "automate" (none falls below the 0.5 data support threshold); `card_unblock_request` and `card_replacement_request` hand off by design. Clarifying paths are sized inside each flow (23.2% of transactions unclassifiable in statement totals; 32.0% of customers lacking a credit score or income; no complaint names a transaction).
- Unmapped volume 0%; no stop condition fired. Escalation (about 10%), hour of day (flat), and complaint outcomes (flat across categories) are generator properties. Digital errors are followed by a contact within 24 hours no more often than other events (0.43% against 0.42%).
- Transcripts: 42 distinct customer texts from two balance templates, Cramer's V 0.008 with the contact reason. Every one of the 600 sampled items is a balance question, so the machine pre-labels mark all 450 non-`account_inquiry` items as not matching their workflow.

#### Decisions

- [ADR 0023](adr/0023-workflow-prioritization-method.md): pre-registered weighted scoring, with a labeled structured proxy for the automatable share while human labels are pending, and weight and mapping sensitivity.
- [Workflow prioritization](decisions/workflow-prioritization.md): build and depth order `account_inquiry`, `card_support`, `dispute`, `credit`; `credit` is the weakest candidate for depth and the first cut candidate, then `card_support`.
- Weights are the prompt defaults, committed before results; the human may adjust them later as a new version.
- The automatable share counts only labeled items whose text matches the workflow; `unclear` counts as not automatable; machine pre-labels live in a separate file with `review_status=pending` and are never read as labels; a rerun never overwrites a labeled file.
- Pain leaves out sentiment (constant `neutral` on transactional contacts); its complaint component is the SLA breach rate.
- Cost assumptions are stated team figures with derivations (`assumption: true`, `verified: false`), reported at 0.5, 1, and 1.5 times; costs never enter the score. The label-based addressable cost reads "pending human labels".
- Local hours use fixed country offsets (MX UTC-6, CO UTC-5, AR UTC-3); the lag baseline is a deterministic 5% md5 sample of non-error events.
- Dependency: matplotlib 3.11.2 (Matplotlib license, PSF-based) with pillow 12.3.0 (MIT-CMU), fonttools 4.66.0 (MIT), kiwisolver 1.5.1 (BSD), contourpy 1.4.0 (BSD), cycler 0.12.1 (BSD), pyparsing 3.3.3 (MIT), pinned in `uv.lock`; size is pending action 13.

Deviations from the prompt and plan, found during implementation:

- Analysis logic lives in `data_platform/src/bank_data/analysis/` (typed, tested, covered) rather than directly in `data_platform/analysis/`, which holds the inputs and a README with the code map.
- The generated scores are a separate report (`docs/analysis/workflow-scores.md`) next to `workflow-evidence.md`, plus `analysis-results.json` for later phases; the decision document is written by hand from them.
- The mapping CSV carries `source`, `value`, `subcategory`, and two scenario columns besides the prompt's `workflow_id`, `sub_intent`, and `rationale`, and maps the dictionary's English spellings of the contact reasons as well.
- The mapping coverage test checks the committed sample, the fixture, and every accepted `reason_category`, because the full delivery is not available in CI; `make analysis` repeats the check on the full data as a stop condition.
- The transcript opening used for the signal check is the first sentence that mentions a balance, because one template opens with a greeting sentence.

#### How to verify

```bash
make check                                                     # needs Docker; never reads .env
make analysis DATA_SOURCE=s3                                   # about 30 seconds on the phase 03 warehouse
git diff --stat docs/analysis                                  # only the header timestamps and commit change
uv run pytest data_platform/tests/unit -k "analysis or mapping" -q
uv run pytest data_platform/tests/integration/test_analysis.py -q
make pipeline && make analysis                                 # offline, on the committed sample; writes under data/warehouse-sample/analysis
```

Results recorded in this phase:

| Check | Result |
|---|---|
| `make check` | Exit 0 |
| Python tests | 1,326 unit and 63 integration tests pass (1,269 and 58 before) |
| Coverage gates | All 11 pass; `data_platform/src` 97.2% (the analysis package 98%) |
| Docs check | markdownlint 0 issues; 23 mermaid blocks in 86 files parse |
| Guards | No emoji; attribution clean; gitleaks found no leaks |
| `make analysis DATA_SOURCE=s3` | 686,296 interactions and 67,095 complaints; about 27 seconds; figures byte-identical on a rerun |
| `make analysis DATA_SOURCE=sample` | Completes offline (the 74-customer sample is not representative: it ranks `card_support` first) |

#### Known limitations

- The automatable share is a proxy (historically simple contacts) until humans label, and transcripts cannot supply labels for `card_support`, `dispute`, or `credit`.
- Three of the four interaction mappings are assumptions; the strict scenario leaves `card_support` and `credit` without interaction demand.
- Rubric values (harm, demo depth, capability) are judgments, written down with reasons.
- Costs are unverified projections; complaint back-office handling time is not in the data and is excluded.
- The data is synthetic and several fields are generator-uniform, so differences between workflows come mostly from the contact reason.

#### Next phase

Phase 05, core banking and identity (`kit/prompts/05-core-banking-identity.md`), seeding all four workflows in the prioritization order. Pending actions 0 and 10 (contract review and prioritization review) should come first; the labeling task (action 11) runs in parallel and does not block.

### Phase 03: data platform (2026-09-26)

Plan: `docs/plans/phase-03.md` (no plan mode, per the orchestrator; open questions decided in the plan and ADRs). Two requirements the human added during the phase are folded in: a readable preview of every table, and an explicit, never-mixed choice between the committed sample and the full data.

#### What was done

| Commit | Change |
|---|---|
| `47d1a05` | The plan, from profiling a full scratch mirror of the bucket |
| `9ed7aa0` | DuckDB, dbt-core 1.12, dbt-duckdb 1.11, Pandera 0.33 (pandas), boto3, pydantic-settings, PyYAML (bank-data); DuckDB (bank-agent); pandas-stubs (dev) |
| `1fb56aa` | Table specs for the 13 tables, strict parsing, strict Pandera schemas, row reasons, schema-evolution detection, canonical codes |
| `a77c989` | `DataSource` port with `S3Source` and `LocalSource`, key-layout parsing, the DuckDB manifest, bronze and quarantine Parquet, the ingestion runner, settings, masking logs |
| `2a4a630` | The dbt project: generated sources and silver contracts, `stg_` and `silver_` models, gold serving, ML inputs, marts, generic tests; the dbt subprocess runner, workspace, and CLI |
| `b541131` | The late-arrival fixture (script with `--check`) and the update-correctness integration tests |
| `2fa34bd` | Available credit for credit cards only; the profiled sign conventions in the domain docstrings |
| `f9eedf3` | Restore `typing._GenericAlias.__call__` after Pandera patches it (regression test) |
| `1eda921` | DuckDB readers over gold Parquet, `GOLD_SCHEMAS`, the `duckdb` contract backend, gold compatibility tests |
| `559d57b` | Byte order marks written as escapes |
| `9d18a52` | Quality report, lineage page, cross-customer product flags, interrupted runs |
| `00a2da8` | Explicit source (`BANK_DATA_SOURCE`, `DATA_SOURCE`), per-source warehouses, the make targets, the sample guard and codegen check in `make check` |
| `e91e22f` | `bank-data sample`, pseudonyms, the provenance README with example rows, the preview, the guard, and the committed sample |
| `38e4831` | Docs (data card, update policy, source layout, pipeline page, ADRs 0007 and 0022, generated quality report and lineage), CI steps, bandit annotations, BACKLOG, this entry |
| `90c5cd7` | Track `docs/data/`: the `**/data/*` ignore rule had hidden it |
| This commit | Final check numbers in this entry |

#### Key data findings (phase 04 builds on these)

| Topic | Finding |
|---|---|
| Layout | 7,671 CSV objects (5.3 GB), one delivery on 2026-08-31: six root snapshots and seven daily-partitioned facts (2023-06-17 to 2026-06-17; `campaign_sends` from 2023-07-01) |
| Row counts | transactions 4,425,008; digital_events 15,620,994; call_center_interactions 686,296; call_transcripts 171,321; satisfaction_surveys 212,759; complaints 67,095; campaign_sends 1,746,801; customers 150,000; products 400,000; daily_exchange_rates 13,164; service_agents 1,200; branches 350; marketing_campaigns 200 (23.5 million rows) |
| Duplicates | None: 0 exact and 0 primary-key duplicates in every table (the announced ~2% is absent); uniqueness violations only on `product_number` (6) and `employee_code` (13) |
| Late arrivals and schema evolution | None in the delivery (single write date, `process_date` always equals the key, identical headers); proven on the fixture instead |
| Nulls | Random ~5% in many optional columns; structural nulls elsewhere (`amount_usd` 57%, null on every USD row; `transaction_category` 61%; `merchant_name` 77%; `landline_phone` 50%); `call_transcripts.duration_seconds` 14% null although required, so 24,029 transcripts are quarantined |
| Orphans | `customers.registration_branch_id` 149,995 of 150,000 and `service_agents.assigned_branch_id` 831 of 833; every other foreign key resolves. `complaints.affected_product_id` always names another customer's product (44,570 of 44,570), `digital_events.product_id` almost always |
| Contact reasons | Six coarse values, identical to `reason_category`: Transaccional 240,056 (35.0%), Producto 150,863 (22.0%), Queja 117,021 (17.1%), Técnico 102,899 (15.0%), Comercial 54,879 (8.0%), Retención 20,578 (3.0%). Resolution is lowest for Queja (43.6%); escalation is about 10% for every reason |
| Text | Transcripts open with one of two balance-inquiry sentences whatever the topic; `detected_intents` is always `consulta_general`; complaint descriptions have five templates. No Portuguese |
| Time | Timestamps are UTC and `process_date` is a UTC-6 business date (rows from 00:00 to 06:00 roll to the next calendar day in all countries) |
| Snapshots | One snapshot of `customers` and `products`, not monthly: phase 10 needs another label strategy |
| Money | Balances and amounts are never negative (credit balance convention `balance_is_amount_owed`); no MXN products (Mexican customers hold USD) |

#### Decisions

- [ADR 0007](adr/0007-dbt-duckdb-and-pandera-for-the-data-platform.md): dbt-duckdb and Pandera for the data platform, and when to move to a lakehouse.
- [ADR 0022](adr/0022-committed-bounded-data-sample.md): the committed, bounded, pseudonymized sample, the preview, and the explicit data source.
- Credit balance convention `balance_is_amount_owed` (data card); available credit for credit cards only; transfers and adjustments stay unclassified (all amounts positive); no masking needed for `merchant_name` (only purchases carry it, with 24 business names).
- Bronze keeps raw strings; typing, trimming, and empty-to-null happen in silver. A file is a breaking type change when at least half its non-empty values in a column fail to parse. Additive-column backlog items go to the manifest, never into tracked files.
- Incremental facts reprocess every partition loaded since the last run plus a 7-day lookback, over all versions of the affected keys, with `delete+insert` on the primary key; a re-delivery that drops keys triggers a full refresh.
- Timestamps are UTC; the snapshot date is 2026-06-17 and balances are as of 2026-06-18T05:59:59Z.
- Dependencies (all permissive and maintained, pinned in `uv.lock`): duckdb 1.5.5 (MIT), dbt-core 1.12.5 and dbt-duckdb 1.11.0 (Apache-2.0), pandera 0.33.1 (MIT) with pandas 3.0.6 (BSD-3-Clause), boto3 1.43.103 (Apache-2.0), pyyaml 6.0.3 (MIT) for bank-data; duckdb for bank-agent (gold readers); pandas-stubs 3.0.5 (BSD-3-Clause, dev) so the pandas code stays under strict mypy. Sizes are pending human action 9.

Deviations from the plan text, found during implementation:

- The whole-object glob in bronze was replaced by computed paths after the first full ingest ran quadratically slow (the path follows from the key); changing the snapshot date now needs a fresh warehouse.
- `affected_product_id` and `product_id` cross-customer references were found while building the sample, so silver gained `has_foreign_affected_product` and `has_foreign_product`, and complaints are served without a foreign product reference.
- The sample takes at least 70 customers and five complaints (complaints without a product reference are rare), giving 74 customers.
- Pandera's global patch of `typing._GenericAlias.__call__` broke `CustomerId("...")` in the shared pytest process; the original method is restored after import.
- `data_platform/tests/unit/test_cli.py` became `test_bank_data_cli.py` (a mypy module-name clash once `data_platform/tests` joined the mypy path).
- The sample README carries no timestamp or git sha so regeneration leaves `git status` clean; the generated reports do carry both.

#### How to verify

```bash
make check                                          # needs Docker; never reads .env
make pipeline                                       # from the committed sample, offline (about 30 seconds)
make data-sample && make data-sample && git status  # needs the s3 warehouse; tree stays clean
make pipeline-sample DATA_SOURCE=s3                 # 2,000 customers of the full delivery
make pipeline DATA_SOURCE=s3 && make data-report DATA_SOURCE=s3 && make lineage DATA_SOURCE=s3
uv run pytest data_platform/tests/integration/test_update_correctness.py -q   # incremental equals full
uv run pytest services/api/tests/contracts -q -k duckdb                       # DuckDB readers pass the suites
```

Results recorded in this phase:

| Check | Result |
|---|---|
| `make check` | Exit 0 |
| Python tests | 1,269 unit and 58 integration tests pass (1,166 and 16 before) |
| Coverage gates | All 11 pass; `data_platform/src` 96.4%, adapters 99.7% |
| Full ingestion (S3) | 7,671 objects, 23,471,159 rows to bronze, 24,029 quarantined, 0 failed; about 8 minutes download and 12 minutes validation; a second run lists 7,671 unchanged in 4 seconds |
| Full build (S3) | 41 models, a seed, 273 tests: PASS 313, WARN 2 (the two orphan branch references), ERROR 0; 2 minutes 8 seconds (1 minute 7 seconds incremental) |
| `make pipeline-sample DATA_SOURCE=s3` | Completes; 17 seconds for 2,000 customers |
| `make pipeline` from the sample with S3 variables blanked | Completes offline in about 30 seconds; 783 objects, 2,470 rows, 0 quarantined |
| `make data-sample` twice | Byte-identical; `git status` clean |
| Committed sample | 74 customers, 2,470 rows plus 125 preview rows (2,595 of 5,000); every coverage case present; the guard passes |
| Docs check | markdownlint 0 issues; 23 mermaid blocks in 77 files parse |
| Guards | No emoji; attribution clean; gitleaks found no leaks |

#### Known limitations

- The delivery is static: late arrivals, re-deliveries, and schema evolution are proven on the synthetic fixture, not observed live; freshness thresholds are prototype values.
- One snapshot of customers and products; `credit_risk_inputs` cannot give phase 10 a label after its features (BACKLOG).
- The DuckDB readers are not wired into the composition root; phase 05 selects backends and seeds PostgreSQL from gold (BACKLOG).
- The committed sample over-represents rare statuses by construction and is not a statistical sample; final numbers come from the full delivery.
- The UTC reading of timestamps is an inference from the data, not a documented fact.
- Contract changes need affected objects re-ingested by hand (BACKLOG: `--revalidate`).
- The organizer data-use terms are unchecked (phase 17).

#### Next phase

Phase 04, data analysis and workflow selection (`kit/prompts/04-analysis-workflow-selection.md`), on the gold marts of the full delivery (`make pipeline DATA_SOURCE=s3`). Phases 05, 06, and 09 should still wait for the team's review of the phase 02 and 02b entries (pending action 0).

### Phase 08: LLM gateway, composable reliability, and the prompt registry (2026-09-26)

Plan: `docs/plans/phase-08.md` (no plan mode required for this phase, per the orchestrator). Phase 08 ran before phases 03 to 07 because `.env` does not exist yet; it depends only on the phase 02 and 02b ports and fakes. Human decision for this phase: the provider is undecided, so nothing calls a live provider and no cassette was recorded.

#### What was done

| Commit | Change |
|---|---|
| `f59d49b` | The plan |
| `c3b4d2d` | `pyyaml` as a runtime dependency, the optional `litellm` extra, `types-pyyaml`, the mypy override, and `--all-extras` in the CI audit |
| `a1c56ae` | `domain/llm_outputs.py` (seven output models, `FallbackIntentLabel`, the forbidden prompt variable names), canonicalization moved into `domain/intelligence.py`, `LlmCallContext.sensitive_terms`, `PromptTemplate` owner and changelog, `LlmProviderRejectedError` |
| `eaa2b9c` | `FilePromptRegistry` and the eight version 1 prompts with the prompts README |
| `5b06e8f` | `PromptedLLMClient` (JSON Schema from the output model, one repair), `LiteLLMCompletion` and `LiteLLMClient`, `UnconfiguredLLMClient`, `Redactor`, `CassetteLLM` |
| `3ce6975` | Timeout, bounded retry, circuit breaker, fallback, budget guard, cost accounting, tracing, and redaction decorators; `services/api/config/llm_prices.yaml` |
| `1f21440` | New `LLM_*` settings and production rules, `bootstrap/llm.py`, the container wiring, 32 hand-authored fixture cassettes and their generator, `bank_evals.language_checks`, the integration test, conformance entries |
| `3370bb0` | `docs/architecture/llm-gateway.md`, `docs/security/prompt-injection.md`, ADR 0013, README and index updates, BACKLOG rows |

#### Review summary

- **Port.** Unchanged from phase 02: `generate_structured` and `generate_text` return the value or text with usage, latency, model id, prompt reference, `repaired`, and `cost_usd`. Errors are the six LLM types, plus `LlmProviderRejectedError`, a non-retryable subtype of `provider_error` for 4xx rejections and "no provider configured".
- **Stack order (outermost first).** Redaction, budget guard, tracing, cost accounting, fallback (only with a fallback model), then per provider circuit breaker, bounded retry (at most 2, transient errors only, exponential backoff with jitter), timeout. The prompt's order is kept; cost accounting and fallback, which it did not place, sit where tracing and the budget see the cost and each provider keeps its own breaker. A test walks the chain.
- **Providers.** `fake` uses a client injected through `LlmOverrides`, otherwise `UnconfiguredLLMClient`; `cassette` replays (record mode wraps LiteLLM and is refused in production); `litellm` needs the extra, a model, and a key per model.
- **Budget.** Per-session token cap, per-conversation cost cap (`LLM_CONVERSATION_BUDGET_USD`, new, default 0.50), daily cost cap. The guard reserves the worst-case reply before a call and keeps the reservation after `invalid_output` or a timeout.
- **Prices.** Only in YAML, with `source_url` and `verified`. Unverified entries cost 1.5 times the listed price, unknown models the highest listed prices times 1.5, rounded up to eight decimals.
- **Redaction.** Emails, CURP, CPF, CNPJ, keyword-introduced CC, DNI, RG, and other document numbers, card numbers, phones, dot-grouped numbers and 8+ digit runs unless next to a currency marker, session names, and names after phrases such as "me llamo" or "meu nome e". Allowlisted keys (`UNREDACTED_VARIABLE_KEYS`) pass unchanged.
- **Prompts.** `extract_dispute_slots`, `extract_account_inquiry_slots`, `extract_card_support_slots`, `extract_credit_slots`, `classify_intent_fallback`, `detect_escalation_signals`, `phrase_response` (text), `summarize_for_handoff`, all version 1. The registry refuses any input named after a risk estimate, a credit profile fact, or an internal flag; `phrase_response` declares only the outcome code, the rendered reasons, and the disclaimer for credit.
- **Tracing.** GenAI semantic conventions 1.37.0 attributes through the `Telemetry` port on a `gen_ai.chat` span; content capture off by default and refused in production.

#### Decisions

- [ADR 0013](adr/0013-litellm-behind-a-port-with-composable-decorators.md): LiteLLM behind the port with composable decorators.
- `FakeLLM` stays in `bank_agent.testing` (the phase 02 open question): the composition root accepts an injected client and otherwise uses `UnconfiguredLLMClient`, so production code never imports test doubles.
- The cassette key includes the session language in addition to the prompt id, version, model id, and variables, because the same variables in es and pt must give different replies. The JSON field is `cassette_id`, because gitleaks flags a 64-hex value under a `key` field.
- A missing cassette raises `CassetteMissingError`, a configuration error outside the LLM family, so a caller's fallback cannot swallow it.
- Dependencies: `pyyaml` 6.0.3 (MIT, already locked through bandit) becomes a direct runtime dependency for prompt front matter and prices; `types-pyyaml` 6.0.12.20260906 (Apache-2.0) joins the dev group; `litellm` 1.102.1 (MIT) is an optional extra because it measured 84 MB (170 MB with dependencies; human review item 8). `pip-audit` over every extra reports no known vulnerabilities.

Deviations from the plan text, found during implementation:

- The redaction decorator lives in `adapters/llm/redaction.py` next to the `Redactor` rather than in its own module.
- `BoundedRetryDecorator` takes an optional sleep function so the composition root can pass a non-waiting one in tests.
- The Portuguese check lives in `bank_evals.language_checks` (evaluation code), because phase 14 reuses it on recorded replies; its tests read the committed cassettes.
- Fixture cassettes are generated by `scripts/write_fixture_cassettes.py` (the hand-authored content lives there), and a test compares its output with the committed files byte for byte.

#### How to verify

```bash
make check                                                              # needs Docker running; never reads .env
uv run pytest services/api/tests/unit/adapters/llm services/api/tests/unit/adapters/test_prompt_registry.py -q
uv run pytest services/api/tests/unit/bootstrap/test_llm_composition.py -q     # stack order and provider selection
uv run pytest services/api/tests/integration/test_llm_gateway_stack.py -q      # full stack, sockets disabled
uv run python scripts/write_fixture_cassettes.py --check                       # fixture cassettes are current
uv run python -c "import importlib.util; print(importlib.util.find_spec('litellm'))"   # None: the extra is not installed
```

Results recorded in this phase:

| Check | Result |
|---|---|
| `make check` | Exit 0 |
| Python tests | 1166 unit tests (855 before this phase) and 16 integration tests (11 before) pass; no test opens a network socket or calls a provider |
| Coverage gates | All 11 pass: domain 99.7%, ports 100%, adapters 99.9%, api 97.4%, bootstrap 100%, testing 100%, evals 100%; policy and application report `no statements yet` |
| Import contracts | 5 kept |
| Docs check | markdownlint 0 issues; 19 mermaid blocks in 66 files parse |
| Guards | No emoji; attribution clean; gitleaks found no leaks |
| Audit | `pip-audit` over all packages and every extra (litellm included): no known vulnerabilities |

#### Known limitations

- No live provider has been exercised; the LiteLLM request shape and error mapping are tested with an injected completion function. The first live run must happen after the human chooses a provider and reviews the extra.
- Every cassette is a hand-authored fixture and says so; they test parsing, replay, and coverage, not model quality.
- The Portuguese check is lexical: it catches Spanish leakage, not awkward phrasing.
- The budget ledger is per process (BACKLOG, phase 15).
- Name redaction covers known session names and introduced names only; workflow code must still keep names out of variables.
- No workflow calls the gateway yet; callers, fallbacks, clause texts from the policy pack, and the grounding verifier for handoff summaries are phase 09 work (BACKLOG).

#### Next phase

Phase 03, data platform (`kit/prompts/03-data-platform.md`), once the human creates `.env` (pending action 2). Phases 04, 05, and 10 need 03's gold tables, and phase 06 reads phase 04's prioritization decision, so none of them runs cleanly first; phase 06 could start early only if the human accepts that gap. Phases 05, 06, and 09 should still wait for the team's review of the phase 02 and 02b entries (pending action 0).

### Phase 02b: multi-workflow domain and contracts (2026-09-26)

Plan: `docs/plans/phase-02b.md`, approved 2026-09-26 by the orchestrator under the human's standing delegation, with every recommendation for open questions 1 to 5, 8, and 9 accepted, question 6 answered yes (the `handoff()` builder pins `schema_version` `1.0.0`, a new `handoff_v1_1()` builder exists, and the pinned test body is unchanged), and question 7 answered yes (`jsonschema` as a dev dependency).

#### What was done

| Commit | Change |
|---|---|
| `d7ac151` | The approved plan |
| `367c2f9` | `jsonschema` 4.26.0 in the dev dependencies |
| `9fd5586` | Golden `1.0.0` handoff, execution record, decision, and scenario documents, frozen from the phase 02 builders, with tests against the models and the committed schemas |
| `ca8027a` | `AddedIn` marker, the `required` schema hook on `DomainModel`, and the version gate, with a negative control; no schema changed |
| `5680be9` | `WorkflowId`, ten new intents, `CROSS_WORKFLOW_INTENTS`, the workflow catalog, `escalation.py` with the card and credit codes, clause families `ACC`, `CRE`, `ELG`; every contract moved to `1.1.0` |
| `0ed46c5` | Optional product balance fields, `BalanceView`, `available_credit` over an explicit convention, `PaymentStatusView`, `StatementSummary`, `TransactionQuery.types`; enriched contract fixture rows |
| `4bb8b13` | `CardAction`, `CardBlockReason`, `CardStatusView`, `CardRequest`, `CARD_ACTION_HANDLING`, `BlockCardArguments.reason` |
| `a4ba91a` | `CreditProduct`, `CreditProfile`, `CreditApplicationIntake` and its lifecycle, the credit identifiers, id kinds, source tables, and two errors |
| `2dff782` | `CreditRiskFeatures`, `RiskEstimate`, `EligibilityAssessment`, `EligibilityView`, `ServiceRef`, `CreditReview`, the record entries, `ModelComponent.RISK_ESTIMATOR`, two dependency errors |
| `e1c0714` | `submit_credit_application` (action, arguments, tool), seven more tools, the new `AssistantResponse` parts and the one-confirmation rule, the vocabulary test, the problem mapping tests |
| `81b8f3a` | Handoff and execution record `1.1.0` fields and validators |
| `42aa03c` | Scenario `1.1.0`, the changelog rows, and the serialization decision in `contracts/README.md` |
| `dcf28ec` | `RiskEstimator`, `EligibilityPolicy`, `CreditProductCatalog`, `CreditProfileReader`, `CreditApplicationRepository`, workflow-aware `get_bound` |
| `230edb2` | Memory credit repositories and catalog, `credit_profiles` and `credit_applications` on the unit of work, `FakeRiskEstimator`, `FakeEligibilityPolicy`, credit fixtures, four contract suite modules |
| `3c30edd` | `workflow-registry.md`, `credit-separation.md`, domain model and ports pages, ADRs 0020 and 0021 |

#### Review summary

- **New intents and owners.** `account_inquiry`: `balance_inquiry`, `payment_status`, `statement_request`. `card_support`: `card_status`, `card_block`, `card_unblock_request`, `card_replacement_request`. `dispute`: `dispute_new`, `dispute_status`. `credit`: `credit_product_info`, `credit_eligibility`, `credit_application`, `credit_application_status`. Cross-workflow: `informational`, `unsupported`, `human_request`, `greeting_or_other`. A test fails when an intent has no owner.
- **Card escalation-only actions.** A protective block is a self-service write (confirmation, step-up, verified read-back) from `card_support` and `dispute`. Unblock and replacement requests have no tool and go to a human with `card_unblock_requested` or `card_replacement_requested`.
- **Credit application statuses.** `submitted` to `under_human_review` or `withdrawn`; `under_human_review` to `withdrawn` or `closed`. No approved or declined status. A customer can only withdraw; reviewer moves arrive in phase 13. A submitted intake is a review item of its own, not a handoff.
- **Eligibility outcomes and review reasons.** Outcomes `indicatively_eligible`, `not_eligible`, `review_required`, `insufficient_data`. Review reasons `missing_income`, `missing_credit_score`, `borderline_risk_interval`, `risk_estimate_unavailable`, `days_past_due_present`, `amount_above_review_threshold`, `customer_contests_result`, and `product_requires_human_assessment` (mortgages are information only). A missing fact never yields `indicatively_eligible`; a missing estimate or an `unknown` band yields `review_required`.
- **Risk estimate visibility.** Agents and evaluators see the estimate (handoff credit review, execution record); customers see only the outcome, reasons, uncertainty statement, review path, and disclaimer. Every estimate field and the credit score, income, days past due, and utilization are `Internal`; nothing internal is sent to a model.
- **Contract bumps.** handoff, execution_record, decision, scenario, and policy_clause are now `1.1.0`. Fields added in a minor version carry `x-added-in` and are not required, so stored `1.0.0` documents validate against the new schemas (tested with golden documents and `jsonschema`).

#### Decisions

- [ADR 0020](adr/0020-four-workflows-and-the-workflow-registry.md): four workflows and the workflow registry.
- [ADR 0021](adr/0021-credit-risk-and-eligibility-separation.md): separating conversation handling, risk estimates, and the synthetic eligibility service.
- Serialization-mode defaults: the `AddedIn` marker, recorded in `contracts/README.md`.
- `PolicyRepository.get_bound` takes the workflow (no implementation or caller existed).
- Dependency added (dev group only): `jsonschema` 4.26.0 (MIT), with `referencing` 0.37.0 (MIT), `rpds-py` 2026.6.3 (MIT), `attrs` 26.1.0 (MIT), and `jsonschema-specifications` 2025.9.1 (MIT), a few MB installed. Reason: validating stored contract documents against the generated schemas. Phase 09 still decides the runtime dependency.

Deviations from the plan text, found during implementation:

- The dependency and the golden documents landed as two commits, so the phase has 16 commits instead of 15.
- The contract fixture enrichment (balances, payment types) landed with the account views, because the type filter suite needs it; the new credit tables landed with the adapters as planned.
- `CardActionConfirmation` lives in `conversation.py` and carries no product type; `cards.py` stays free of `actions` imports so `BlockCardArguments` can use `CardBlockReason`.
- `StatementSummary` counts pending, declined, and reversed transactions as `not_settled_count` and totals only approved ones, a rule the plan left implicit.
- `CreditApplicationIntake.declared_monthly_income` (and the matching argument and request fields) carry `Pii("financial")`; the plan left the marker open.
- `EligibilityView` carries the missing fact names, so an `insufficient_data` answer can ask for exactly what is missing.
- Credit fixtures live in `services/api/tests/bank_agent_credit.py`, next to the other shared test support modules.
- The ADR index notes that numbers 0007 to 0019 are reserved.

#### How to verify

```bash
make check                                                      # needs Docker running; never reads .env
make contracts && git diff --exit-code contracts/               # schemas are current
uv run pytest services/api/tests/contracts -q                   # every memory adapter and fake passes its suite
uv run pytest services/api/tests/unit/domain/test_contract_compatibility.py evals/tests/unit/test_scenario_compatibility.py -q
uv run lint-imports                                             # five contracts kept
```

Results recorded in this phase:

| Check | Result |
|---|---|
| `make check` | Exit 0 |
| Python tests | 855 unit tests (612 before this phase; 108 of them contract-suite tests, 75 before) and 11 integration tests pass; every phase 02 test passes without edits |
| Coverage gates | All 11 pass: domain 99.7%, ports 100%, adapters 100%, api 97.4%, bootstrap 100%, testing 100%, evals 100%; policy and application report `no statements yet` |
| Import contracts | 5 kept |
| Contracts | `make contracts` leaves no diff; golden `1.0.0` documents validate against the `1.1.0` schemas |
| Docs check | markdownlint 0 issues; 17 mermaid blocks in 53 files parse |
| Guards | No emoji; attribution clean; gitleaks found no leaks |

#### Known limitations

- The eligibility and estimator ports run only against the fakes until phases 06, 09, and 10; the credit repositories run only on the memory backend until phases 03 and 05.
- Available credit is not computed until phase 03 records the credit balance sign convention; transfers and adjustments are `unclassified` in statement totals until phase 03 profiles amount signs.
- `response_code` is not interpreted (no code table in the data).
- Entry states in the workflow catalog are placeholders until phase 09.
- A re-serialized `1.0.0` document carries the `1.1.0` keys at their defaults and so fails the `1.0.0` schema; consumers upgrade first, as before.
- Agents can read only applications that a handoff references until phase 13 adds the review methods.

#### Next phase

Phase 08, LLM gateway (`kit/prompts/08-llm-gateway.md`), then phase 03 once `.env` exists. Phases 05, 06, and 09 should wait for the team's review of this entry and the phase 02 entry.

### Phase 02: domain model, ports, and contracts (2026-09-26)

Plan: `docs/plans/phase-02.md`, approved by the human on 2026-09-26 with every open-question recommendation (trust keyed by session lineage; length caps plus a single-paragraph summary for handoff text; `FakeLLM` in `bank_agent.testing` with the `LLM_PROVIDER=fake` wiring left to phase 08; client-supplied UUID turn ids; `first_name` as the only personal data in `Customer`; channels `web_chat`, `agent_console`, `evaluation_harness`; the scenario model in `bank_evals`; the staleness test as a unit test; the case lifecycle table; risk thresholds in the domain; intake-time complaint fields only).

#### What was done

| Commit | Change |
|---|---|
| `650ca1c` | The approved plan |
| `086e38b` | Value objects (`Money`, `Currency`, `ExchangeRate`, `Country`, `Language`, `Locale`, typed identifiers, `SourceRef`, `MaskedNumber`, `AuthLevel`, `Role`, `Channel`, `AccessContext`), the error taxonomy, ADR 0004 |
| `cefecf4` | Entities (`Customer`, `Product`, `Transaction`, `HistoricalComplaint`, `DisputeCase`, `Session`, `Conversation`, `Turn`), identity challenges, `TrustState`, workflow concepts (`Intent`, `TransactionDescriptor`, `DisputeReason`, `Decision`, `ActionRequest`, `ActionResult`, `Verification`, `Outcome`), `AssistantResponse` and `TurnResult`, the `Handoff` and `ExecutionRecord` models, `FixedClock`, ADR 0005 |
| `fe0761f` | Every port (repositories with reader Protocols, unit of work, audit log, session store, identity, determinism, LLM client, prompt registry, policy repository, retriever, router, resolver, language detector, model registry, telemetry); `SystemClock`, `RandomIdGenerator`, `NoopTelemetry`; the remaining test doubles; two import-linter contracts for `bank_agent.testing`; a 90% coverage gate for it |
| `aa0933d` | In-memory adapters for every repository port, the unit of work, and the session store; the shared contract suites; the port conformance test |
| `cf438ea` | `bank_evals.scenarios.model.Scenario` (scenario v1); `bank-evals` depends on `bank-agent` |
| `d169203` | `scripts/generate_contracts.py`, `make contracts`, the five schemas in `contracts/schemas/`, the staleness and no-reasoning-field tests, `contracts/README.md`, ADR 0006 |
| `b106405` | `api/domain_problems.py`: domain error families mapped to problem types, installed by default |
| `f8e5df8` | Whitespace fix in `docs/plans/kickoff-notes.md` (merged from the team repository), so `make docs-check` passes |
| `51bb92f` | `docs/architecture/domain-model.md`, `docs/architecture/ports-and-adapters.md`, README and index updates |

#### Domain model summary for review

- **Money:** `Decimal` amount plus explicit currency; floats rejected; arithmetic only within one currency and exact (an inexact result raises); conversion only through `ExchangeRate`; banker's rounding only in `rounded()`. JSON carries amounts as strings.
- **Identity and access:** repositories are bound to an `AccessContext` (role plus customer or staff id) through a unit of work, and no repository method accepts a customer id; another customer's record behaves like a missing one. Sessions store expiry instants (idle, absolute, step-up window) and answer every expiry question from an instant; the raw token never enters the domain (stores look up by digest).
- **Trust state:** append-only events keyed by session lineage (kept across rotation and re-authentication into the same conversation), stored outside the turn's transaction; the risk tier (low, elevated, high) never decreases.
- **Dispute case lifecycle:** `opened` to `in_review`, `escalated`, or `rejected`; `in_review` to `resolved`, `rejected`, or `escalated`; `escalated` to `in_review`, `resolved`, or `rejected`; `resolved` and `rejected` are terminal; no `opened` to `resolved`.
- **Success needs evidence:** a positive `Verification` needs an evidence reference, a verified action status in a response needs evidence, and a verified action in a handoff must have executed and been confirmed.
- **Personal data:** `Customer` carries only `first_name`; document numbers, phones, emails, and addresses stay in the phase 05 identity adapter. Fraud label and score are `Internal`. Customer and record text is `UntrustedText`.

#### Handoff schema summary for review (`contracts/schemas/handoff.v1.json`)

`schema_version`, `handoff_id`, `created_at`, `conversation_ref`, `case_ref`, `state_at_escalation`, `language` (es or pt), `jurisdiction`, `customer_ref` (internal id only), `auth` (level, expires_at), `request` (summary of at most 500 characters on one paragraph, intent), `verified_facts` (fact plus a mandatory `table:id` source, at most 20), `actions_taken` (action, target, confirmed, status executed or failed or unknown, verification verified or not_verified or mismatch, evidence), `policy_basis` (`clause_id@version`), `escalation_reason` (code from a fixed list, detail), `open_questions` (at most 10), `customer_sentiment`, `priority`, `sla_due`. Unknown keys are rejected at every level, which is how transcript fields are refused, and no output contract has a reasoning field.

#### Decisions

- [ADR 0004](adr/0004-money-and-currency-handling.md): money and currency handling.
- [ADR 0005](adr/0005-trust-state-append-only.md): trust state as append-only evidence with a monotonic risk tier.
- [ADR 0006](adr/0006-handoff-and-execution-record-contracts.md): handoff and execution record contracts, with no chain-of-thought field.
- No third-party dependency was added. `bank-evals` gained a uv workspace dependency on `bank-agent` (lockfile change only).

Deviations from the plan text, found during implementation:

- `InvariantViolation` is named `InvariantViolationError` (ruff N818), and the planned `InvalidMoneyError` became `MoneyPrecisionError`, because construction failures surface as Pydantic `ValidationError` and the only behavioral money failure is an inexact result.
- `SessionStore.save(session)` replaces the planned `touch`, `set_step_up`, and `revoke`: the domain methods (`touched`, `with_step_up`, `revoked`) build the new session and the store persists it, so the rules live in one place.
- `DomainModel.evolve` was added because `model_copy(update=...)` skips validation; every entity change goes through it.
- Serialization-mode schemas mark every field as required (`json_schema_serialization_defaults_required`), because serialized documents always carry every field.
- Idempotent case creation compares the request (transaction, reason, amount) rather than the stored case, so replaying a request after the case moved on still returns it.
- `RandomIdGenerator` uses 128 random bits in hex rather than base32.
- The plan's test that validates a handoff against the generated schema dictionary needs a JSON Schema validator, which is not installed; the schema is generated from the model that validates the handoff, and adding a validator is in `docs/BACKLOG.md` for phase 09.
- Shared test support lives in `services/api/tests/bank_agent_builders.py` and `services/api/tests/bank_agent_contracts.py` (unique module names, importable under `--import-mode=importlib`).
- A conformance test (not in the plan) checks through mypy that every implementation satisfies its port and at runtime that every port docstring states preconditions, postconditions, errors, and isolation; the phase 01 `ReadinessCheck` docstring gained the missing sections.
- The work landed in 9 commits instead of the planned 12: the entity, workflow, and contract models share one commit because their tests share builders.
- The human merged `docs/plans/kickoff-notes.md` from the team repository during the phase (commit `8d4123f`); only its whitespace was changed.

#### How to verify

```bash
make check                                                      # needs Docker running; never reads .env
make contracts && git diff --exit-code contracts/               # schemas are current
uv run pytest services/api/tests/contracts -q                   # every memory adapter passes its suite
uv run pytest services/api/tests/unit/domain -q                 # domain unit and property tests
uv run lint-imports                                             # five contracts kept
```

Results recorded in this phase:

| Check | Result |
|---|---|
| `make check` | Exit 0 |
| Python tests | 612 unit tests (including 75 contract-suite tests on the memory backend) and 11 integration tests pass |
| Coverage gates | All 11 pass: domain 99.6%, ports 100%, adapters 100%, api 97.4%, bootstrap 100%, testing 100%, evals 100%; policy and application report `no statements yet` |
| Import contracts | 5 kept, each with a negative control |
| Docs check | markdownlint 0 issues; 10 mermaid blocks in 46 files parse |
| Guards | No emoji; attribution clean; gitleaks found no leaks |

#### Known limitations

- Only the memory backend runs the repository contract suites; DuckDB readers (phase 03) and PostgreSQL adapters (phase 05) must be added to `READ_BACKENDS` and `WRITE_BACKENDS`.
- The router, resolver, and language detector suites run only against scripted fakes until phases 09 and 10.
- Ports for identity, prompts, policy, retrieval, and the model registry have no implementation yet (phases 05 to 10).
- In-process ports are synchronous; a remote implementation would need an async variant.
- A newer minor version of a contract fails an older validator because unknown keys are rejected; producers and consumers must upgrade together (documented in `contracts/README.md`).
- Superseded on 2026-09-26: the human chose four workflows (`account_inquiry`, `card_support`, `dispute`, `credit`); CLAUDE.md section 1 records the decision, and phase 02b extends these contracts additively.

#### Next phase

Phase 03, data platform (`kit/prompts/03-data-platform.md`). It needs the organizer S3 values in `.env` (pending action 2). Phases 05, 06, and 09 should wait for the team's review of this phase's domain model and handoff schema.

### Phase 01: monorepo scaffold and quality gates (2026-09-26)

Plan: `docs/plans/phase-01.md`, approved with the decisions listed at its top (no license yet; mermaid, jsdom, and mypy approved despite the 50 MB rule; Node 24.21.0; pnpm instead of npm; testcontainers in CI and locally; `bank_owner` as the development owner; extra coverage gates; MD032 and MD060 off; guard scripts on uv-managed Python 3.12).

#### What was done

Ten commits, `f40f180` to the commit that adds this entry:

| Commit | Change |
|---|---|
| `f40f180` | uv virtual workspace root with shared ruff, mypy, import-linter, pytest, coverage, and bandit configuration; the four packages with typer CLIs (`bank-agent`, `bank-data`, `bank-ml`, `bank-eval`) exposing `version` and `--help`; the root `conftest.py` that classifies tests by directory and blocks the network for unit tests |
| `728adac` | `bank_agent`: layer packages with READMEs; `bootstrap/settings.py` (five settings classes, production rules); `bootstrap/logging.py` (structlog JSON with a redaction processor, also for uvicorn and other standard-library loggers); `bootstrap/container.py`; `ports/health.py`; the PostgreSQL readiness adapter; `api/` (app factory, request id middleware, RFC 9457 problem registry, `/health/live`, `/health/ready`); entry points `asgi.py` and `cli.py`; unit tests, including a negative control for the import-linter contracts |
| `bb32902` | `apps/web`: Vite 8, React 19, TypeScript 6 strict, Tailwind CSS v4, ESLint 9 (typescript-eslint strict type-checked, react-hooks, jsx-a11y strict, boundaries), Prettier, Vitest with jsdom, Testing Library, and MSW; layer READMEs; the neutral shell; a fixture-based boundary test |
| `bcd45ac` | `docker-compose.yml` (postgres always on; `api`, `web`, `obs`, and `ml` profiles; every image pinned; ports on 127.0.0.1); `deploy/postgres/init/10-roles.sh`; observability configs; both `Dockerfile.dev`; integration tests for readiness and database roles through testcontainers |
| `ec3e2a4` | `scripts/checks/check_coverage_gates.py`; tests for `check_env_keys.py`, the gate checker, and the emoji check |
| `073b3e3` | `.markdownlint-cli2.jsonc`, `scripts/checks/check_mermaid.mjs`, and its `node:test` self-test |
| `7fe0faa` | `Makefile` (help, setup, up, down, check, lint, format, typecheck, test-unit, test-integration, test-web, env-check, docs-check); extended and autoupdated `.pre-commit-config.yaml`; `scripts/hooks/run_web_tool.sh` |
| `7310d43` | `.github/workflows/ci.yml` with the python, web, guards, and audit jobs |
| `a075f45` | CLAUDE.md switched from npm to pnpm (human-authorized): the frontend stack line, the supply-chain rule, and the note that later prompts saying npm or npx mean pnpm or `pnpm dlx` |
| `edd8ff3` | Root README, `docs/README.md`, `docs/architecture/overview.md`, ADRs 0001 to 0003 with the index, `SECURITY.md`, `CONTRIBUTING.md`, and the pull request template |

The five phase 00 backlog items owned by phase 01 are resolved and removed from `docs/BACKLOG.md`: the `make env-check` target, pytest tests for `check_env_keys.py`, the Node version decision (Node 24 LTS through `engines` `>=24.15.0 <25` and `.nvmrc` `24`), `pre-commit autoupdate`, and running the guard scripts on the uv-managed Python 3.12.

#### Decisions

- [ADR 0001](adr/0001-record-architecture-decisions.md): record architecture decisions in MADR format.
- [ADR 0002](adr/0002-uv-workspace-and-hexagonal-backend.md): uv workspace monorepo and hexagonal backend layers, including the entry points outside the layers, global strict mypy, and per-layer coverage gates.
- [ADR 0003](adr/0003-frontend-layering-and-state.md): frontend layering, state rules, and ESLint enforcement.
- Package manager: pnpm 10.33.0 (human decision), pinned through `packageManager`, with `apps/web/pnpm-workspace.yaml` declaring that the lifecycle scripts of `msw` (browser worker copy) and `unrs-resolver` (fallback binary download) are not needed.
- Large dev dependencies approved by the human despite the 50 MB rule: mermaid 12.0.0 (123 MB unpacked; with jsdom and markdownlint-cli2 the docs tooling adds about 240 MB to `node_modules`, whose total is about 450 MB) and mypy 2.3.1 (about 63 MB installed).
- TypeScript 6.0.3 instead of 7.0.2 (typescript-eslint 8.70.1 requires below 6.1) and ESLint 9.39.5 instead of 10.x (eslint-plugin-jsx-a11y supports ESLint 9 at most).
- The development and test owner role is the image bootstrap role `bank_owner`; a non-superuser production owner is deferred to phase 16.

Dependencies added, all permissively licensed and maintained; exact versions are in `uv.lock` and `apps/web/pnpm-lock.yaml`:

- Python runtime (`bank-agent`): fastapi 0.141.1, pydantic 2.13.5, pydantic-settings 2.15.0, uvicorn[standard] 0.54.0, structlog 26.1.0, typer 0.27.2, sqlalchemy[asyncio] 2.1.1, asyncpg 0.31.0. The other three packages depend on typer only.
- Python dev group: pytest 9.1.1, pytest-asyncio 1.4.0, pytest-socket 0.8.1, pytest-cov 7.1.0, hypothesis 6.168.1 (MPL-2.0, dev only), testcontainers 4.15.0, httpx 0.28.1, ruff 0.16.9, mypy 2.3.1, import-linter 2.15, bandit 1.9.4, pip-audit 2.10.1.
- Web: react and react-dom 19.3.0; dev: vite 8.3.1, @vitejs/plugin-react 6.1.1, typescript 6.0.3, tailwindcss and @tailwindcss/vite 4.3.3, eslint and @eslint/js 9.39.5, typescript-eslint 8.70.1, eslint-plugin-react-hooks 7.1.1, eslint-plugin-react-refresh 0.5.7, eslint-plugin-jsx-a11y 6.10.2, eslint-plugin-boundaries 7.2.0, eslint-import-resolver-typescript 4.4.5, eslint-config-prettier 10.1.8, globals 17.12.0, prettier 3.9.9, vitest and @vitest/coverage-v8 5.0.2, jsdom 30.1.1, Testing Library (react 16.3.3, dom 10.4.2, jest-dom 7.0.1, user-event 14.6.7), msw 2.15.0, markdownlint-cli2 0.23.3, mermaid 12.0.0, @types/react and @types/react-dom 19.3.0, @types/node 24.19.0.

Deviations from the plan text, found during implementation:

- mypy runs once over every package with `explicit_package_bases` instead of once per package, because per-package runs still collided on `services/api/tests/conftest.py` and `services/api/tests/integration/conftest.py`. The root `conftest.py` is checked in a second run.
- `ApiConfig` is passed to `create_app` next to the provider instead of being a `ServiceProvider` property, because `bootstrap` may not import `api`, so the container cannot build it; `bank_agent.asgi` builds it from settings.
- The boundary test lives in `apps/web/tooling/boundaries.test.ts` (with a fixture tree beside it) rather than `src/test/`, because it uses Node APIs that the browser tsconfig does not include.
- The "features only through `index.ts`" rule is the last policy of `boundaries/dependencies` (`fileInternalPath: '!(index.ts)'`) instead of the separate `boundaries/entry-point` rule, which is deprecated in eslint-plugin-boundaries 7.
- Shared test doubles live in `services/api/tests/bank_agent_test_support.py`, importable through the pytest `pythonpath` setting, because `--import-mode=importlib` does not put test directories on the path.
- The compose `api` service reads `.env` optionally and receives the database values explicitly, so `docker compose config` works from shell variables alone.
- `pre-commit autoupdate` selected gitleaks v8.30.0 for the hook; the gitleaks binary used by `make check` and CI is 8.30.1.
- Two bandit findings in `scripts/checks/check_no_emoji.py` (importing `subprocess`, running `git` from PATH with a fixed argument list) carry `nosec` annotations with a justification comment.

#### How to verify

```bash
make setup
make check                                   # needs Docker running; never reads .env
uv run bank-data --help && uv run bank-ml --help && uv run bank-eval --help && uv run bank-agent --help
pnpm --dir apps/web run build
POSTGRES_ADMIN_PASSWORD="$(openssl rand -hex 16)" POSTGRES_APP_PASSWORD="$(openssl rand -hex 16)" \
  docker compose up -d --wait postgres       # becomes healthy; then: docker compose down -v
```

Results recorded in this phase:

| Check | Result |
|---|---|
| `make setup` then `make check` in a fresh clone with no `.env` | Both exit 0 |
| Python tests | 170 unit tests and 11 integration tests pass |
| Coverage gates | All 10 pass: ports, adapters, bootstrap, and the three CLI packages at 100%, api at 97.3%; domain, policy, and application report `no statements yet` |
| Web tests | 17 tests pass (shell, MSW setup, boundary policies); `pnpm run build` succeeds |
| Docs check | markdownlint 0 issues; 5 mermaid blocks in 37 files parse |
| Guards | No emoji; attribution clean for `HEAD`; gitleaks found no leaks |
| Audits | pip-audit and `pnpm audit --prod --audit-level high`: no known vulnerabilities |
| Workflow lint | actionlint 1.7.7 reports no findings for `ci.yml` |
| Compose, postgres | Healthy with throwaway passwords; `bank_app` is not a superuser and has no `BYPASSRLS`; `app` is owned by `bank_owner` |
| Compose, all profiles | `api` healthy and `/health/ready` returns `database: ok` with JSON logs carrying request ids; the web dev server serves and proxies `/health/live`; Jaeger, Prometheus (scraping the collector), Grafana, and MLflow respond; stack removed with `down -v` |
| Deliberate violations | A domain module importing the API breaks two import-linter contracts; a page importing a feature internal fails ESLint; an emoji fails the emoji check; a malformed diagram fails the Mermaid check with its file and line |

#### Known limitations

- The CI workflow has not run on GitHub yet, because nothing was pushed. It passed actionlint, and every step mirrors a local `make check` step that passes.
- The domain, policy, and application layers are empty, so their coverage gates are satisfied trivially and say so explicitly.
- The web shell renders only the product name; i18next, the router, TanStack Query, Radix, forms, the generated API client, and vitest-axe arrive in phase 12.
- Readiness checks only the database; health endpoints do not yet reflect other dependencies (phase 15).
- The web development image installs pnpm through corepack at build time and runs `pnpm install` at container start, so both need network access.
- Hot reload inside containers on macOS may need polling; the fallbacks are documented in `deploy/README.md`.

#### Next phase

Phase 02, domain model and contracts (`kit/prompts/02-domain-contracts.md`), in plan mode.

### Phase 00: bootstrap and guardrail verification (2026-09-26)

Plan: `docs/plans/phase-00.md`.

#### What was done

- Verified the toolchain, skills, attribution settings, ignore rules, and hooks without installing anything.
- Ran the guard self-tests on scratch files and recorded the outputs below.
- Fixed a `.gitignore` defect: `data/` excluded the directory itself, so the existing `!data/.gitkeep` negation had no effect. The rule is now `**/data/*`, which still ignores the contents of every `data` directory at any depth. Added `data/.gitkeep`.
- Added `scripts/checks/check_env_keys.py`, which reports `set` or `unset` for every name documented in `.env.example`, never a value, and exits 1 when a required name is unset.
- Created this file, `docs/BACKLOG.md`, and `docs/plans/`.

#### Environment report

| Tool | Version | Notes |
|---|---|---|
| git | 2.55.0 | |
| uv | 0.11.17 | |
| Python | 3.12.13, uv-managed | System `python3` is Homebrew 3.14.7; the guard scripts are stdlib-only and run under it through pre-commit |
| Node | v24.14.1 | Newer than the preferred 22 LTS; see `docs/BACKLOG.md` |
| npm | 11.11.0 | |
| Docker | 29.8.0, daemon running | |
| Docker Compose | v5.5.1 | |
| pre-commit | 4.6.2 | pre-commit and commit-msg hooks installed; `core.hooksPath` unset |
| gitleaks | 8.30.1 | The pre-commit hook pins v8.21.2 until phase 01 runs `pre-commit autoupdate` |
| AWS CLI | 2.36.26 | Optional; ingestion uses boto3 |
| go | 1.26.1 | Builds the gitleaks pre-commit hook |
| libomp | 23.1.2 | LightGBM prerequisite |

Skills present under `.claude/skills/`: `design-taste-frontend`, `minimalist-ui`, `full-output-enforcement`.

Settings: `.claude/settings.json` sets `attribution.commit` and `attribution.pr` to empty strings and `attribution.sessionUrl` to `false`. A gitignored `.claude/settings.local.json` allows `git commit *`; the project deny rules for `--no-verify` and `-n` still apply. Loaded setting sources from `/status`: pending human action.

Ignore rules: `git check-ignore -v` confirms `.env`, `.env.*` except `.env.example`, `data/` contents, `kit/`, `mlruns/`, `node_modules/`, `dist/`, `.coverage`, `coverage.xml`, `htmlcov/`, `apps/web/coverage/`, and `*.duckdb`. Nothing under `kit/` is tracked; the only tracked file under `data/` is `data/.gitkeep`.

Secret hygiene: `.env` does not exist yet (checked for existence only, never read). Running `python3 scripts/checks/check_env_keys.py` in the repository prints the notice `.env not found; checking the process environment only`, reports all 9 required names as unset, and exits 1.

#### Guard self-test results

| Test | Command | Result |
|---|---|---|
| Attribution stripping | `python3 scripts/hooks/strip_ai_attribution.py msg.txt` on a scratch message containing `Co-Authored-By: Claude Opus <noreply@anthropic.com>` and `Generated with [Claude Code](https://claude.com/claude-code)` | Printed `strip-ai-attribution: removed attribution lines from the commit message`, exit 0. The file kept only the subject and body; a grep for either line found 0 matches |
| Emoji check, failing case | `python3 scripts/checks/check_no_emoji.py emoji.txt` on a file written by Python with U+1F600 | `emoji.txt:1:7: emoji character U+1F600 is not allowed`, `check-no-emoji: 1 emoji character(s) found`, exit 1 |
| Emoji check, passing case | `python3 scripts/checks/check_no_emoji.py CLAUDE.md` | exit 0 |
| Attribution history | `scripts/checks/check_no_ai_attribution.sh` | `check-no-ai-attribution: clean for range 'HEAD'`, exit 0 |
| All hooks | `pre-commit run --all-files` | gitleaks, large files, private key, merge conflict, end of file, trailing whitespace, and emoji hooks all passed |
| Secrets in history | `gitleaks git --redact .` | no leaks found |

Environment key check self-tests, all with scratch env files and an emptied process environment, never the real `.env`:

| Case | Result |
|---|---|
| Every required name set to a unique sentinel, mixing quoted, `export`, and inline-comment forms | exit 0, `all 9 required variable(s) set`, 0 sentinel strings in the output |
| `SESSION_SECRET` empty with a trailing comment, `CSRF_SECRET` absent | exit 1, both reported `unset`, `2 of 9 required variable(s) unset`, 0 sentinel strings in the output |
| Env file does not exist | notice printed, process environment used, exit 1 |
| Name set only in the process environment | reported `set`, value not printed |

#### Decisions

- `.gitignore` uses `**/data/*` instead of `data/` so that `data/.gitkeep` can be tracked. Approved by the human with the phase plan. No ADR: this is a correction, not a choice between alternatives.
- The required variable set for `check_env_keys.py` is the S3 values, both PostgreSQL passwords, and the session and CSRF secrets. The LLM keys stay optional while `LLM_PROVIDER=fake`. Approved by the human.
- No dependencies were added.

#### How to verify

```bash
pre-commit run --all-files
python3 scripts/checks/check_no_emoji.py
scripts/checks/check_no_ai_attribution.sh
gitleaks git --redact .
git ls-files kit data          # expected: data/.gitkeep only
python3 scripts/checks/check_env_keys.py
```

#### Known limitations

- `make check` does not exist until phase 01, so this phase used the commands above as its substitute.
- `check_env_keys.py` has manual self-tests only; automated tests are in `docs/BACKLOG.md` for phase 01.
- `/status` output and `.env` creation are pending human actions.

#### Next phase

Phase 01, monorepo scaffold and quality gates (`kit/prompts/01-scaffold.md`), in plan mode.
