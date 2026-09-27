# Phase 10a plan: shared ML foundations, the learned intent router, and the transaction resolver

Status: not a plan-mode phase. The human delegated approvals to the orchestrator; every open question below is decided by the session with the reasoning recorded. Written against commit `a94873d` (after session 09b). Session 10b (the credit risk estimator) is out of scope; the shared foundations are built so 10b reuses them unchanged.

## Scope

Tasks 1 to 13 and 23 to 24 of `kit/prompts/10-learned-components.md` for the router and the resolver: shared foundations (`ml/src/bank_ml/common`), the router (`ml/src/bank_ml/router`), the resolver (`ml/src/bank_ml/resolver`), the `bank_agent` adapters `router:tfidf`, `router:embeddings`, and `resolver:lgbm` loaded through a filesystem `ModelRegistry`, the CLI, `make train`, model cards, generated evaluations, and ADRs 0015 and 0016.

## Facts that shape the design

- Transcripts cannot label intents: 42 distinct customer texts, all balance questions, `detected_intents` constant (phases 03 and 04, `docs/analysis/labeling-protocol.md`). Router text is therefore team-authored seed utterances plus documented deterministic augmentation, each item labeled with its provenance. The transcript analysis the prompt asks for (contact reason distribution, agreement with `detected_intents`) is still computed and reported, as the evidence for that choice.
- No language model provider is chosen (`LLM_PROVIDER=fake`). The paraphrase step is built behind the gateway with cassette support and is skipped with a stated reason until a provider exists; no cassette is fabricated.
- The API image has no numpy, scikit-learn, or LightGBM (and must not gain them). Artifacts are therefore plain JSON parameters (TF-IDF vocabulary, idf, and coefficients; LightGBM trees from `dump_model`), evaluated in pure Python inside `bank_agent`. No pickle is ever loaded, and the registry checks a SHA-256 digest before parsing.
- Inference-time feature code lives in `bank_agent` (`adapters/models/text_features.py`, `resolver_features.py`) and training imports it, so training and serving cannot skew. The resolver's descriptors come from the same deterministic understanding functions the engine uses (`application/understanding`).
- Gold has 4.4 million transactions for 150,000 customers (about 33 each over three years, 24 merchant names). Candidate sets inside a dispute window are small; results are reported by candidate count, and headline resolver metrics use queries with at least two candidates.

## Files to create or change

| Path | Change |
|---|---|
| `ml/pyproject.toml` | Dependencies: `bank-agent` (workspace), scikit-learn, LightGBM, datasketch, rapidfuzz, numpy, duckdb, mlflow-skinny, pyyaml |
| `services/api/pyproject.toml` | `rapidfuzz` becomes a runtime dependency (merchant similarity at inference; small, MIT) |
| `ml/src/bank_ml/common/` | `seeds.py` (fixed seeds), `hashing.py`, `splits.py` (group hash split, temporal cutoff with a gap, stratified seed-group split), `dedup.py` (normalization, MinHash LSH, cross-split removal), `cards.py` (dataset cards), `leakage.py` (post-outcome denylist and guard), `metrics.py` (classification, ranking, ECE, reliability, coverage-risk, cluster bootstrap), `calibration.py` (temperature scaling), `thresholds.py`, `tracking.py` (MLflow, SQLite store), `registry.py` (publish and promote through the filesystem registry), `reports.py` (Markdown helpers, git sha), `llm.py` (gateway construction for offline generation) |
| `ml/corpus/router/` | `seeds/<intent>.yaml` (team-authored, es-MX, es-CO, es-AR, pt-BR), `lexicon.yaml` (slots, slang, fillers, homophones), `validation/` (the 200-item sheet) |
| `ml/src/bank_ml/router/` | `corpus.py`, `augment.py`, `perturb.py`, `dataset.py`, `transcripts.py`, `models.py` (majority, keyword, TF-IDF, embeddings), `evaluate.py`, `report.py`, `paraphrase.py`, `validation.py`, `command.py` |
| `ml/src/bank_ml/resolver/` | `gold.py`, `describe.py` (es and pt templates), `dataset.py`, `models.py` (rules, LightGBM lambdarank), `evaluate.py`, `silver.py`, `report.py`, `command.py` |
| `services/api/src/bank_agent/adapters/models/` | `registry.py` (`FilesystemModelRegistry`, `FilesystemModelStore`), `text_features.py`, `tfidf_router.py`, `embedding_router.py`, `resolver_features.py`, `tree_ensemble.py`, `lgbm_resolver.py` |
| `services/api/src/bank_agent/bootstrap/` | `models.py` (select router and resolver by name and version or alias, falling back to the rule baselines when no artifact exists), `settings.py` (`WORKFLOW_ROUTER`, `WORKFLOW_RESOLVER`, `WORKFLOW_MODEL_REGISTRY_DIR`), `workflows.py` |
| `services/api/src/bank_agent/prompts/` | `paraphrase_router_seed/1.md` (training paraphrases) and `paraphrase_router_eval/1.md` (the evaluation paraphrase set; a different prompt, per the labeling protocol), with output models in `domain/llm_outputs.py` |
| `Makefile`, `.gitignore`, `.env.example` | `make train`, `make promote`; `mlruns.db`; the new settings |
| Docs | `ml/README.md`, `docs/models/router.md`, `docs/models/resolver.md`, `docs/evaluation/router.md` and `resolver.md` (generated), `docs/evaluation/router-labeling.md`, ADRs 0015 and 0016, READMEs, BACKLOG, PROGRESS |

## Router design

- **Labels.** The 17 `Intent` values. Workflow level: the owning workflow, `shared` (`informational`, `human_request`, `greeting_or_other`), or `out_of_scope` (`unsupported`, covering both unsupported banking requests and off-domain text, each seed tagged with its scope).
- **Seeds.** 8 per intent and locale (es-MX, es-CO, es-AR, pt-BR): 544 team-authored seeds, some with slots (`{amount}`, `{merchant}`, `{date}`, `{last4}`, `{product}`). Seed id `intent:locale:NN`.
- **Augmentation** (seeded per seed id, documented in the dataset card): the canonical fill, three slot substitutions from locale lists, regional slang substitution, keyboard typos, casing and punctuation noise, and dropped accents. Provenance `team_authored` or `augmented_from:<seed_id>` with the augmentation kind.
- **Splits.** Seeds whose canonical texts are near-duplicates (MinHash LSH, Jaccard at least 0.6 on character 4-gram shingles) are merged into one seed group first. Groups are split per (intent, locale) cell by a salted hash order: 2 test, 1 dev, 5 train of 8. All augmentations follow their group. Then dev and test items that are near-duplicates of train items (Jaccard at least 0.8) are removed and counted. The test split is never used for tuning.
- **Guard.** A unit test builds the dataset from the committed corpus and fails on any seed group in two splits, any exact normalized duplicate across splits, or any cross-split pair at or above the threshold.
- **Models.** Majority class; `router:keyword@1`; TF-IDF (word 1-2 grams and character 2-5 grams from the shared analyzer, sublinear tf) with multinomial logistic regression, C chosen on dev; multilingual-e5-small embeddings with logistic regression (ml extra; skipped with a recorded reason when absent). Temperature scaling on dev for both learned models.
- **Metrics.** Accuracy, macro-F1, per-intent precision and recall, workflow-level accuracy and the workflow confusion matrix, ECE and a reliability chart, the coverage-risk curve, per language, locale, and workflow, each with the item count, the seed-group count, and a 95% cluster bootstrap interval over seed groups (items of one seed are correlated). High-stakes recall (`dispute_new`, `card_block`, `card_unblock_request`, `card_replacement_request`, `credit_application`, `human_request`) is reported separately: a miss there skips a write, a protective action, or a handoff.
- **Threshold.** On dev only: the lowest confidence threshold whose intent error rate among covered items is at most 5%, maximizing coverage. Below it the engine asks which workflow (the existing `below_threshold` path).
- **Robustness.** Speech-to-text perturbations of test seeds (dropped accents, homophones, fillers, truncation); dialect slices; the Spanish-to-Portuguese transfer gap (train on Spanish only, test on pt-BR); in-distribution against out-of-distribution (held-out dialect and noisy text). The paraphrase set is pending a provider.
- **Human validation.** A stratified 200-item sheet (intent by locale) with a protocol; agreement and label accuracy are computed when labels exist and reported as pending otherwise.

## Resolver design

- **Queries.** Target transactions sampled from gold with a seeded hash. Two uses, reported separately: `dispute` (purchases, withdrawals, and adjustments; candidates are the customer's transactions inside the country's dispute window, `DSP-*-1`: MX 90, CO 60, AR 30 days) and `payment_lookup` (payments and transfers; candidates are the customer's payments and transfers inside the `ACC-ALL-2` window, 92 days). The reference instant is the target time plus a hashed offset of 0 to 20 days.
- **Splits.** Customers are split 70/15/15 by a salted hash of the customer id (no customer in two splits). A temporal cutoff (default 2026-01-01) with a 30-day gap: train and dev reference instants fall before the cutoff, test reference instants after the cutoff plus the gap, from test customers only.
- **Descriptions.** Deterministic templates in es (per country) and pt: exact, rounded, or slang amounts ("15 lucas", "quinientos varos", "cem reais"), relative and explicit dates, exact, misspelled, or partial merchant names, channel hints, and partial information (at least one clue). The ground truth is the target id. Descriptors are extracted by the engine's deterministic understanding functions. Paraphrases through the gateway are pending a provider.
- **Features** (shared, `resolver_features.py`): amount given, absolute and relative amount difference, currency match, date given, days outside the resolved range, merchant fuzzy similarity (rapidfuzz on folded text), inferred category match, channel match, recency in days and rank, same-day count, amount closeness rank, candidate count.
- **Models.** `resolver:rules@1` as shipped; LightGBM lambdarank (fixed seed, one thread, deterministic), boosting rounds chosen by early stopping on dev. Scores become per-query softmax probabilities; `clear_winner` needs the top minus runner-up probability at the margin threshold. A descriptor with no clue yields an empty ranking (the workflow asks for detail), like the rules baseline.
- **Metrics.** Top-1 accuracy and MRR; at the margin threshold chosen on dev (the lowest margin whose wrong-transaction rate among auto-selected queries is at most 2%), the coverage, the wrong-transaction rate, and the correct-clarify rate (the true transaction among the three options shown when the resolver does not auto-select). By use, language, country, and candidate count, with bootstrap intervals over queries.
- **Silver labels.** Complaints in `Transactions` and `Fees` with a claimed amount, matched to the customer's own transactions by currency, amount (within 1%), and a 60-day window before the complaint. `affected_product_id` is never used (it always names another customer's product, BACKLOG). A 100-item verification sheet goes to `data/labeling/` (gitignored, organizer-derived); precision is pending until labeled. Silver results are a secondary evaluation only, and circular in the amount (stated).

## Registry, promotion, and serving

- **Layout** under `WORKFLOW_MODEL_REGISTRY_DIR` (default `data/artifacts/models`, gitignored): `<component>/<name>/versions/<version>/{artifact.json,manifest.json}` and `<component>/<name>/aliases/<alias>.json`. The version is the first 12 hex digits of the artifact's SHA-256, so an identical retrain yields the same version. `resolve` verifies the digest (`ModelArtifactIntegrityError`) and raises `ModelArtifactNotFoundError` for an unknown name, version, or alias.
- **Promotion.** `train` registers every learned model and points `candidate` at it; `promote --approved-by NAME` compares the candidate's dev and test metrics with the current champion (or the rule baseline when there is none), requires a better primary metric (macro-F1 for the router, top-1 for the resolver) and no loss above 2 points in high-stakes recall or in the wrong-transaction rate, then moves `champion` and appends a promotion record (metrics compared, decision, approver, time, git sha).
- **Serving.** `WORKFLOW_ROUTER` accepts `keyword@1`, `tfidf@<version or alias>`, `embeddings@<version or alias>`; `WORKFLOW_RESOLVER` accepts `rules@1`, `lgbm@<version or alias>`. Defaults stay `keyword@1` and `rules@1`: the learned models are not yet measured end to end on the scenario suite (phase 14), and the scenario tests must not depend on whether a local artifact exists. A missing artifact, or the embeddings router without the ml extra, falls back to the rule baseline with a structured warning; the execution record names the model that actually answered. A digest mismatch stops startup.

## Tracking and reproducibility

Every training run logs to MLflow (default `sqlite:///mlruns.db`, gitignored; this resolves the BACKLOG row about the file store): parameters, metrics, dataset hashes, git sha, Python and library versions, and the dataset card, evaluation JSON, and artifact as artifacts. Seeds are fixed (`bank_ml.common.seeds`). A reproducibility test retrains on a fixture twice and compares metrics within tolerance (and artifact digests).

## Tests to add

- Unit (`ml/tests/unit`): split determinism and group isolation, the temporal gap, the dedup threshold behavior, the leakage guard (including a scan of the feature modules), text and resolver feature functions, threshold selection on synthetic score distributions, ECE and temperature scaling, the perturbation and augmentation functions (determinism, provenance), the corpus guard on the committed seeds, templates and descriptors, metrics and bootstrap.
- Unit (`services/api`): the registry (tmp_path), the tree evaluator, the TF-IDF and embedding routers on tiny hand-written artifacts, resolver features, the bootstrap selection and fallback, settings validation.
- Integration (`ml/tests/integration`): a small fixture corpus and a synthetic gold fixture end to end (build, train, register, promote, load through the `bank_agent` adapters, predict); the pure-Python tree evaluator against LightGBM's own predictions; the reproducibility test.
- Contract: `FilesystemModelRegistry` passes a new `ModelRegistry` suite; `router:keyword`, `router:tfidf`, `resolver:rules`, and `resolver:lgbm` join the router and resolver suites.

## Risks

- Seeds written by one team (and one author style) overstate accuracy on real customers; every report says the text is team-authored and augmented, and the human review and paraphrase set are pending actions.
- The keyword baseline and the seeds share an author pool; the baseline may be favored or disfavored by phrasing. Stated as a limitation.
- Small candidate sets make the resolver look easier than production; reported by candidate count.
- `make check` time: training runs only in integration tests on small fixtures; the full `make train` is not part of `make check`.

## Decisions on open questions

1. **Seeds instead of transcripts** (the prompt's `contact_reason` labels). Transcripts carry no intent signal; the transcript analysis is reported, and training uses seeds. Evaluation text is never produced by the prompt that produced training text (two paraphrase prompts).
2. **Merging rare intents.** Every intent has the same number of seeds by construction, so no merge applies. The port returns an `Intent`, so a workflow-level label cannot be served; the build refuses an intent under the minimum (4 train seed groups) instead of merging silently.
3. **Artifacts as JSON, evaluated in pure Python** rather than pickled scikit-learn and LightGBM objects: no ML libraries in the API image, no unsafe deserialization, and a digest check before parsing. An equivalence test guards the evaluators.
4. **`rapidfuzz` in the API runtime** (about 3 MB, MIT, maintained) because merchant similarity is an inference feature.
5. **Defaults stay on the rule baselines** until phase 14 measures the learned models end to end; switching is a settings change (`WORKFLOW_ROUTER=tfidf@champion`).
6. **Promotion approver.** `make promote APPROVED_BY=...` is explicit; this session promotes under the human's delegation and records that as the approver.
7. **MLflow adapter for `ModelRegistry`** stays optional and is not built (BACKLOG); the filesystem adapter is the default the prompt names.
8. **Language model zero-shot reference** (optional in the prompt) is not run: no provider. BACKLOG row for the phase that records cassettes.
9. **The lingua detector** stays pending human action 22; this session measures `language_detector:lexical@1` on the router corpus, which carries language labels.
