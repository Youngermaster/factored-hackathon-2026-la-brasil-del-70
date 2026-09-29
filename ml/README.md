# bank-ml: learned components

## Responsibility

`bank-ml` builds datasets, trains, evaluates, and promotes the learned components that the API loads through its `ModelRegistry` port:

- the intent router (`router:tfidf`, `router:embeddings`), session 10a;
- the transaction resolver (`resolver:lgbm`), session 10a;
- the credit risk estimator (`risk_estimator:logreg`, `risk_estimator:lgbm`), session 10b: a snapshot risk estimate on synthetic data, never a lending decision.

The API never imports this package. It loads registered JSON artifacts by name and version, or by an alias (`champion`, `candidate`), so a model can be replaced without any workflow change. Model cards: [`docs/models/router.md`](../docs/models/router.md), [`docs/models/resolver.md`](../docs/models/resolver.md), [`docs/models/risk-estimator.md`](../docs/models/risk-estimator.md). Generated evaluations: [`docs/evaluation/router.md`](../docs/evaluation/router.md), [`docs/evaluation/resolver.md`](../docs/evaluation/resolver.md), [`docs/evaluation/risk-estimator.md`](../docs/evaluation/risk-estimator.md).

## Layout

| Path | Content |
|---|---|
| `src/bank_ml/common/` | Seeds, salted hashing, group, temporal, and stratified splits, MinHash near-duplicate removal, dataset cards, the post-outcome leakage guard with the risk label and protected-attribute denylists, metrics with cluster bootstrap intervals, temperature scaling, dev-only threshold selection, MLflow tracking, registry promotion, paths |
| `src/bank_ml/router/` | Seed corpus loader, augmentation and perturbations, dataset and guard, models, evaluation, robustness and transfer, transcript analysis, paraphrase generation through the gateway, validation sheet, report, CLI |
| `src/bank_ml/resolver/` | Gold reader, description templates, dataset (labels by construction), LightGBM ranker, evaluation, silver labels, report, CLI |
| `src/bank_ml/risk/` | Label (cross-sectional, with a forward-looking mode), gold reader with separate feature, label, and slice queries, dataset, logistic regression and monotone LightGBM, calibration, bootstrap and Venn-Abers intervals, numpy scoring checked against the adapter, test evaluation, slices and disparities, test-based promotion, report, CLI |
| `corpus/router/` | Team-authored seeds (`seeds/<intent>.yaml`), the augmentation lexicon, generated paraphrases (`paraphrases/`, when a provider exists), and the human validation sheet |
| `tests/unit/`, `tests/integration/` | Unit tests; end-to-end tests on a small fixture corpus and a synthetic gold warehouse |

Shared with the API (in `bank_agent`, so training and serving cannot skew): `adapters/models/text_features.py` (the router analyzer), `adapters/models/resolver_features.py` (candidate features and the evidence gate), `adapters/models/risk_features.py` (the risk feature vector), `application/understanding/descriptor.py` (the model-off descriptor), the adapters `tfidf_router.py`, `embedding_router.py`, `lgbm_resolver.py`, `learned_risk.py` with `risk_artifact.py`, `tree_ensemble.py`, and the filesystem registry `registry.py`.

## Public interfaces

```bash
make train                                  # router, resolver, and risk train + evaluate (resolver and risk need the s3 gold)
make promote APPROVED_BY="Name Surname"     # champion <- candidate when it wins (risk: on test); the approver is recorded
uv run bank-ml router train|evaluate|promote|paraphrase|export-validation
uv run bank-ml resolver train|evaluate|promote
uv run bank-ml risk train|evaluate|promote
```

- **Outputs.** Artifacts go to `data/artifacts/models` (`WORKFLOW_MODEL_REGISTRY_DIR`), datasets and cards to `data/artifacts/ml/datasets`, evaluation JSON to `data/artifacts/ml/evaluations` (all gitignored), and reports to `docs/evaluation/`.
- **Tracking.** MLflow at `sqlite:///mlruns.db` (gitignored); set `BANK_ML_TRACKING_URI` to override, or `none` to disable.
- **Serving.** The API serves the rule baselines by default; `WORKFLOW_ROUTER=tfidf@champion` (or `embeddings@champion` with the `ml` extra) `WORKFLOW_RESOLVER=lgbm@champion`, and `WORKFLOW_RISK_ESTIMATOR=logreg@champion` (or `lgbm@...`) switch to the learned models; without an artifact the baseline serves.

## How to add a model

1. **Implement the interface.** The port is in `bank_agent/ports/models.py`. Add an adapter in `bank_agent/adapters/models/` that loads a JSON artifact through `read_verified` (digest checked), validates it with a Pydantic model (`extra="forbid"`), and never imports an ML library or unpickles anything. Put any feature code the adapter needs in `bank_agent` so training imports the same function.
2. **Train it.** Add a `fit_*` function next to the existing ones (`router/models.py`, `resolver/models.py`). Fit on train, choose hyperparameters, temperatures, and thresholds on dev only, and export the artifact dictionary.
3. **Register it.** Call `FilesystemModelStore.register(name, artifact, metadata)` with the dev metrics, the baseline's dev metrics, the dataset hash, the git sha, the parameters, and the MLflow run id; then `set_alias(name, "candidate", version, record)`. The version is the artifact's content digest.
4. **Evaluate it.** Add it to the pipeline's `evaluate_all` so it is loaded through the registry and adapter and scored on test next to the baselines. Reports must carry sample sizes and intervals.
5. **Select it.** Add the name to the settings pattern (`ROUTER_SELECTION`, `RESOLVER_SELECTION`, `RISK_ESTIMATOR_SELECTION`) and the loader in `bootstrap/models.py`, with a fallback to the baseline when no artifact exists.
6. **Promote it.** `promote` compares the candidate's dev metrics with the champion's (or the baseline's) under a `PromotionRule` (primary metric plus guards) and records the decision either way. The risk estimator is promoted on test instead (`bank_ml.risk.promotion`, the rule fixed in `docs/plans/phase-10b.md`): a paired bootstrap lower bound of the ROC AUC gain above zero against every reference, with PR AUC, Brier, and ECE guards.

## How to retrain and compare

- **Retrain.** Run `make train`. Seeds are fixed, LightGBM is deterministic with one thread, and identical inputs give identical artifact versions (a reproducibility test checks it). A corpus or gold change gives a new dataset hash, and `evaluate` refuses an artifact trained on another hash.
- **Risk features.** A new risk feature must be an allowlisted `CreditRiskFeatures` field served at inference, added to `risk_features.FEATURE_NAMES` (a new `risk_features@N` id), and pass `assert_risk_features_clean`; days past due, statuses, protected and proxy attributes, and identifiers are refused.
- **Compare two versions.** Use `bank-ml router evaluate --alias <version>` (or `--alias champion`). Each version's manifest (`data/artifacts/models/<component>/<name>/versions/<version>/manifest.json`) holds its dev metrics, and `promotions.jsonl` holds every alias move and refusal. MLflow holds the runs (`mlflow ui --backend-store-uri sqlite:///mlruns.db`, with the full MLflow package).
- **Paraphrases.** Once a provider exists, `bank-ml router paraphrase --purpose train`, then `--purpose eval` (with `LLM_PROVIDER` set, or `cassette` to replay). Then retrain. Generated rows are marked `llm_paraphrased:<seed_id>` with `review_status: pending`.

## Dependencies

scikit-learn, LightGBM 4.7 (MIT, about 5 MB), datasketch 2.0 (MIT, MinHash LSH), rapidfuzz (MIT, also an API runtime dependency for merchant similarity), numpy, duckdb, mlflow-skinny, pyyaml, and `bank-agent`. sentence-transformers stays in the optional `ml` extra of `bank-agent` and is never installed in the API image.

## How to test

```bash
uv run pytest ml/tests -q                   # unit and integration (synthetic fixtures; no warehouse or model download needed)
make test-unit && make test-integration
```

`ml/src` is gated at 80% line coverage by `make check`. The corpus guard (`tests/unit/router/test_corpus_guard.py`) runs on the committed seeds and fails on any leakage across splits.
