# Phase 04 plan: demand evidence and workflow prioritization

Status: no plan mode for this phase (orchestrator instruction, 2026-09-26; the human pre-approved plans, confirmed the four-workflow scope, and delegated open questions). Written against commit `c92dcd8`, after phase 03. Every number comes from the full organizer delivery (`BANK_DATA_SOURCE=s3`, warehouse `data/warehouse/`, delivery `organizer-v1.0.0-2026-08-31`), never from the committed sample.

## Read-only findings that shape the method

Profiled from the phase 03 warehouse before any score was defined.

| Finding | Consequence |
|---|---|
| `contact_reason` has six coarse values equal to `reason_category` (`Transaccional` 35.0%, `Producto` 22.0%, `Queja` 17.1%, `Técnico` 15.0%, `Comercial` 8.0%, `Retención` 3.0%) | The mapping is coarse by construction: one reason stands for several sub-intents. Only `Transaccional` (account inquiries) is an unambiguous match; `Producto`, `Queja`, and `Comercial` are defensible but assumed. The analysis runs a pre-registered mapping sensitivity (primary, strict, alternative) |
| Complaint `category` has five values (`Transactions`, `Fees`, `Service`, `Technical`, `Branch`), each with one `subcategory` (or null, about 10%) | `Transactions / Cargo no reconocido` and `Fees / Cobro indebido` are charge disputes; the rest are `other` |
| Transcripts: 147,292 served, 42 distinct `customer_text` values, all built from two balance questions (credit card balance, savings balance) plus closing phrases; `detected_intents` is always `consulta_general`; `main_topics` equals `contact_reason`; `detected_keywords` is a permutation of `cuenta, servicio, banco` | Transcripts carry no workflow signal. A human label of "resolvable" on them measures the balance question, not the workflow. The labeling protocol therefore also records whether the text matches the workflow stratum, and the automatable share uses only matching items |
| `mentioned_products`: 548,680 references, 545,118 do not resolve and none names the caller's own product | Unusable for splitting coarse reasons into sub-intents |
| `detected_sentiment` is always `neutral` on `Transaccional` contacts | A generator artifact; sentiment is left out of the pain composite |
| Complaint outcomes are flat across categories (SLA breach about 20%, resolution about 15.5 days, repeat complainer about 15%, compensation about 7%, claimed amount present about 33%) | Complaint outcomes cannot rank the workflows; they are reported, and SLA breach enters pain only as the complaint component |
| Outcomes differ by contact reason: first contact resolution from 43.6% (`Queja`) to 91.5% (`Transaccional`); handle time from 221 s (`Transaccional`) to 540 s (`Comercial`); CSAT low share (score 1 or 2) from 20.8% to 54.5% | These are the discriminating pain signals |
| Read-path data: payments 739k and transfers 896k; card products 142k (credit and debit, expiry on about 95%); credit products 130k with `interest_rate` on about 94%; `credit_score` on 85% and income on 80% of customers | No stop condition from the prompt fires |

## Decisions on the open questions

1. **Pre-registered weights.** The prompt defaults (demand 20, pain 25, automatable share 20, harm inverse 10, data support 15, demo depth 10) are committed in `data_platform/analysis/scoring.yaml` together with every formula and rubric value, in a commit before any result is computed. The human may change them later; a change is a new pre-registration version with the reason, and both results are kept.
2. **Automatable share while human labels are pending.** The criterion uses the adjudicated human label share of items whose text matches the workflow, when at least 75 such items exist for the workflow. Otherwise it uses a pre-registered structured proxy: the share of the workflow's historical contacts that were resolved at first contact, not escalated, and needed no follow-up. The proxy is labeled as a proxy wherever it appears. Machine pre-labels are never used.
3. **Labeling.** 150 items per workflow (600), stratified by country (50 each), ranked by a seeded hash, exported to `data/labeling/automatable_sample.csv` (gitignored). Machine pre-labels go to a separate file, `data/labeling/automatable_prelabels.csv`, with `review_status=pending`, so labelers do not anchor on them. A re-export never overwrites a file that already holds human labels. The human labeling is a pending human action, not a blocker.
4. **Cost assumptions.** `data_platform/analysis/cost_assumptions.yaml` holds a loaded cost per handled agent minute per country and an after-call-work factor, each with `assumption: true`, `verified: false`, and the derivation. They are stated team assumptions, not measurements and not taken from a published source.
5. **Where the code lives.** The prompt asks for analysis logic in `data_platform/analysis/`. Python modules live in the package (`data_platform/src/bank_data/analysis/`) so they are typed, linted, tested, and covered; `data_platform/analysis/` holds the analysis inputs (scoring and cost YAML) and a README pointing to the code. Recorded as a deviation.
6. **Generated versus written documents.** `make analysis` regenerates `docs/analysis/workflow-evidence.md`, `docs/analysis/workflow-scores.md`, `docs/analysis/analysis-results.json`, and the figures. The pre-registration, the labeling protocol, the analysis README, and `docs/decisions/workflow-prioritization.md` are written by hand and cite the generated numbers.
7. **Stop condition from the prompt.** The human already confirmed the scope, so the phase continues after the prioritization document. A Blocked entry is recorded only if a workflow has no data support at all.
8. **Local time.** Hours of day use fixed offsets per customer country (Mexico UTC-6, Colombia UTC-5, Argentina UTC-3; none observes daylight saving time in the data period). The UTC reading of timestamps is the phase 03 inference.
9. **Dependency.** matplotlib 3.11.2 for the figures (named by the prompt). With pillow, fonttools, kiwisolver, contourpy, cycler, and pyparsing it adds about 54 MB, at the 50 MB guideline; it is added to `bank-data` only (never the API image) and listed as a pending human review item, as phase 03 did for its footprint.

## Files to create or change

| Path | Change |
|---|---|
| `docs/analysis/workflow-scoring-preregistration.md`, `data_platform/analysis/scoring.yaml` | Criteria, weights, formulas, columns, rubrics, prioritization and sub-intent rules, mapping sensitivity; committed before results |
| `data_platform/mappings/workflow_mapping.csv` | Every observed `contact_reason`, `reason_category` (source and canonical values), and complaint `category`/`subcategory` pair mapped to a `WorkflowId` or `other`, with `sub_intent`, `rationale`, and the strict and alternative scenario columns |
| `data_platform/analysis/cost_assumptions.yaml`, `data_platform/analysis/README.md` | Cost assumptions; index of the analysis inputs |
| `data_platform/src/bank_data/analysis/` | `config.py` (inputs), `stats.py` (bootstrap, kappa, Cramer's V, spikes), `metrics.py` (rates and costs), `scoring.py` (scores, sensitivity, sub-intent classes), `queries.py` (warehouse reads), `evidence.py` (metrics per workflow, demand patterns, segments, lag analysis, data support, stop conditions), `labeling.py` (export, pre-labels, label reading), `figures.py`, `render.py`, `runner.py` |
| `data_platform/src/bank_data/cli.py`, `Makefile` | `bank-data analysis` and `make analysis` |
| `data_platform/pyproject.toml`, `uv.lock` | matplotlib |
| `docs/analysis/README.md`, `labeling-protocol.md`, generated reports and figures | Documentation |
| `docs/decisions/workflow-prioritization.md` | Ranking, build and depth order, sub-intent classes, evidence, risks, breadth risk, what would change the order |
| `docs/adr/0023-workflow-prioritization-method.md`, ADR index | Pre-registered scoring with a structured automatable-share proxy while labels are pending |
| `docs/data/data-card.md`, `data_platform/README.md`, `docs/README.md`, `docs/BACKLOG.md`, `docs/PROGRESS.md` | Updates |

## Tests to add

- Unit: first contact resolution, escalation rate, SLA breach rate, cost per contact and per resolved contact, bootstrap intervals (seeded, hand-checked bounds and degenerate cases), Cohen's kappa, Cramer's V, robust spike detection, criterion normalization, weighted score, sensitivity (12 variants, each renormalized to 100), sub-intent classing, mapping loading and validation, the labeling export (stratification, determinism, no overwrite of labels, pre-label rules), label reading (pending versus labeled).
- Mapping coverage: every `contact_reason` and complaint `category`/`subcategory` in the committed sample and the fixture, and every accepted `reason_category`, has a mapping row; every `workflow_id` and `sub_intent` is a valid `WorkflowId` or `Intent` value.
- Integration: `bank-data analysis` on a warehouse built from the phase 03 fixture writes every expected file.

## Risks

| Risk | Mitigation |
|---|---|
| The mapping is coarse and assumed for three of four workflows | Mapping sensitivity (strict, alternative) reported next to the primary result; the decision document states which conclusions survive |
| The automatable share is a proxy until humans label, and transcripts cannot label three workflows | Proxy labeled everywhere; the label-matching rule makes the limitation measurable; phase 10 is warned that router training text must be team-authored or paraphrased and labeled as such |
| Synthetic generator artifacts (flat complaint outcomes, constant sentiment) could masquerade as findings | Each is reported as an artifact and kept out of the scores |
| Cost assumptions look like facts | `assumption: true`, sensitivity at 0.5x and 1.5x, and "projected" labels |
| Runtime on 15.6 million digital events | The lag analysis is an as-of join in DuckDB; non-error baseline events are a deterministic 5% hash sample, stated in the report |

## Open questions (decided, recorded for review)

- Whether `Producto` should map to `card_support` (primary), `credit` (alternative), or `other` (strict): primary chosen because product-servicing contacts are about existing products and cards are the servicing product with self-service actions; the other two are reported.
- Whether `Queja` contacts belong to `dispute`: primary yes (complaint contacts include contested charges, the only complaint-handling workflow in scope); strict maps them to `other`.
