# Phase 10, session 10b: the learned credit risk estimator

Not a plan-mode phase: the human delegated approvals, so every open question is decided below with its reasoning. The session reuses the session 10a foundations in `ml/src/bank_ml/common` and the filesystem `ModelRegistry`.

Framing, repeated in the model card, the ADR, and every report: this is a risk estimate trained on synthetic organizer data. It is not a lending model, it is not validated for any real credit decision, and it never approves or declines anything. It is one input to the synthetic eligibility service (phase 06), which is also labeled synthetic.

## What the data allows (measured before writing this plan)

- One snapshot of `customers` and `products` (`docs/data/source-layout.md`), so no label can follow its features in time. The estimate is cross-sectional: a **snapshot risk estimate** of a concurrent association, not a forecast and not a default prediction.
- 83,191 customers hold at least one open credit product (credit card, personal loan, mortgage). 2,784 have no known days past due on any of them, and 3,178 more have at least one credit product with unknown days past due.
- Days past due take the values 0, 15, 30, 60, 90, 120, and 180. About 12.4% of credit products are 30 or more days past due, the same for every product type and status.
- Univariate ROC AUC against "any credit product 30 or more days past due", on the 80,407 customers with a known value: credit score 0.495, income 0.502, tenure 0.497, utilization 0.498, credit product count 0.615. The customer rate by credit product count (1: 12.3%, 2: 22.8%, 3: 31.9%) matches `1 - (1 - 0.124)^k`, which is what independent per-product delinquency would give. Country, segment, gender, occupation, education, and marital status rates are all 16% to 18%.
- A prototype (60/20/20 customer split) gave test ROC AUC 0.615 for logistic regression, 0.615 for LightGBM, 0.615 for the credit product count alone, and 0.505 for credit score bands. **The expected result is that LightGBM does not beat logistic regression.** The plan reports whatever the pipeline measures, and the promotion rule below was fixed before any test number from the real pipeline existed.

## Decisions on open questions

1. **Label** (`label_definition` code `snapshot_dpd30_any_credit_product`). The label is positive when any open credit product has days past due of 30 or more at the snapshot date. The population is customers with at least one open credit product whose days past due are known on every open credit product. Customers with no credit product have no label and are out of the population. Customers with a partly unknown value are excluded, so a missing product value cannot hide a positive (3,178 rows, counted in the dataset card). The 30-day threshold is the prompt's example and the first bucket past the 15-day grace value.
2. **Features.** Only allowlisted `CreditRiskFeatures` fields that exist for a customer at the snapshot and are served at inference exactly as in training: `credit_score`, `tenure_months`, `credit_product_count`, and `utilization`. They come from gold `credit_profiles_serving`, the table the API's `CreditProfile` reader serves, and pass through the API's own row mapper and one shared feature function (`bank_agent.adapters.models.risk_features`), so training and serving cannot drift apart. The other allowlisted fields are excluded, and the model card says why:
   - `max_days_past_due` defines the label, so reading it would leak the label.
   - `product_type`, `requested_term_months`, and `requested_amount_to_income` describe an application, and the snapshot has no applications.
   - `monthly_income_usd` is never set by the application (no exchange rates are wired; BACKLOG). Training on it would create a training-serving skew, and income shows no association (AUC 0.502).
   - `jurisdiction` stays a slice: rates are equal across countries (the prompt allows it as a feature only with a justification, and there is none).
3. **Protected and proxy attributes.** Gender, date of birth or age, marital status, detected accent, city, state, postal code, address, segment, occupation, education level, names, contact details, and every identifier are never features. `segment` and `country` are read only by the slice reader, for the disparity report. A guard (`bank_ml.risk.guards`) fails the build, and a unit test fails, if any feature column or feature module names a protected, label-derived, or post-outcome column.
4. **Leakage denylist.** `bank_ml.common.leakage` gains `RISK_LABEL_COLUMNS` and a `days_past_due` substring rule: `days_past_due`, `max_days_past_due`, `days_past_due_at_snapshot`, `products_30_plus_days_past_due_at_snapshot`, plus `customer_status` and `product_status`, which date from the same snapshot as the label and so are not "before" it. Complaints and interactions are not read at all. There is no temporal split (one snapshot); the group split by customer is used alone, and the dataset card says so.
5. **Splits.** Customers are split by salted hash: 60% train, 20% dev, 20% test. The larger dev and test splits than 10a's give 16,000 test customers for tight slice intervals. Dev is halved by a second salted hash:
   - dev-calibration: early stopping, calibrator fits, and Venn-Abers calibration counts;
   - dev-selection: the calibrator choice, the interval method choice, and the dev metrics.

   Test is scored once, by `evaluate`, after every choice is frozen.
6. **Models.**
   - Baselines:
     - `risk_estimator:score_band@1` as shipped, with fixed prior probabilities;
     - the same score bands re-estimated on train (the observed train rate per band);
     - logistic regression (`risk_estimator:logreg`) on the four features: train-median imputation, missing indicators, standardization, and L2 with C fixed at 1.0, because four features on 48,000 rows need no tuning.
   - Candidate: LightGBM (`risk_estimator:lgbm`), binary, seeded, one thread, deterministic, a monotone decreasing constraint on the credit score, rounds chosen by early stopping on dev-calibration log loss.
   - Both learned models export plain JSON and are served in pure Python. Nothing is pickled.
7. **Calibration.** Identity (the model's own sigmoid), Platt scaling, and isotonic regression are fitted on dev-calibration. The one with the lowest dev-selection log loss is chosen per model.
8. **Uncertainty interval.** Two candidates, both computed, chosen on dev-selection:
   - a **bootstrap ensemble**: 20 members, each refit on a customer bootstrap of train and recalibrated on a bootstrap of dev-calibration; the interval is the 2.5% and 97.5% percentiles of the member estimates;
   - **inductive Venn-Abers**: the conformal-family predictor that outputs a probability interval `[p0, p1]`. It is binned on raw-score quantile edges taken from train, with calibration counts from dev-calibration.

   Standard split conformal gives label sets for a binary outcome, not a probability interval, so Venn-Abers is its conformal counterpart here. The pre-registered criterion is group coverage. Group items into ten equal-count groups of the point estimate. A group is covered when its mean interval intersects the 95% Wilson interval of its observed rate. Choose the method with group coverage of at least 0.9 and the smaller mean width; with no method at 0.9, choose the higher coverage. Test reports the same coverage and the stricter "observed rate inside the mean interval" share. Intervals are widened to contain the point estimate.
9. **Bands.** Band cut points come from the policy, not from the model: the pack's `ELG-ALL-2` parameters (0.20 and 0.35) are read at training time and stored in the artifact, and a test checks they still match the pack. "Chosen on dev" becomes: dev-selection reports the population and observed rate per band. The eligibility service keeps reading the band and the interval (a straddling interval is borderline and goes to review), never the raw probability.
10. **Flags.**
    - `missing_features` when any model feature is absent. The estimate still has a band, because the models were trained with missing values.
    - `out_of_distribution` when a present feature falls outside the train range; the band is then `unknown`, so the eligibility service asks for review and never gets a guess. A first-time applicant (zero credit products) is outside the population by definition and therefore out of distribution.
    - `wide_interval` when the interval is wider than 0.10.
11. **Promotion** (the human's instruction: LightGBM must beat the baselines on the held-out test split, never used for tuning, or the champion stays the baseline). `make promote` reads the evaluation of the current candidate (matching artifact version and dataset hash). For each learned candidate against each of its references, it requires:
    - the paired bootstrap 95% lower bound of the test ROC AUC difference above zero;
    - test PR AUC not lower;
    - test Brier score not higher by more than 0.002;
    - test ECE at most 0.03.

    `lgbm` must beat both score-band baselines and `logreg`; `logreg` must beat both score-band baselines. The decision is recorded either way, with the approver "orchestrator (human-delegated approval, session 10b)".
12. **API default.** `WORKFLOW_RISK_ESTIMATOR` accepts `score_band@1` (default), `logreg@<version or alias>`, and `lgbm@<version or alias>`. The default stays `score_band@1`, as in 10a: the learned estimate is measured only offline, its only signal is the credit product count, and it would send every first-time applicant to review. Phase 14 decides after an end-to-end run (BACKLOG). With a learned selection:
    - a missing artifact serves the score-band baseline with a structured warning (the API keeps working on a fresh checkout);
    - a digest mismatch or a malformed artifact stops startup, as in 10a;
    - an estimate that cannot be computed raises `risk_estimator_unavailable`, and the workflow asks for review, never a default estimate.
13. **Slices and disparities.** Test metrics by country, segment, within-country income tertile (cut points from train; "missing" is its own group), and credit product count. Each slice reports its size, positives, prevalence, ROC AUC and calibration gap with bootstrap intervals, and the low-band and review-borderline shares. Cells with fewer than 300 customers or 30 positives are flagged small. A group is listed for investigation when, against the rest of the population, its calibration gap differs by more than 0.02 with a bootstrap interval that excludes zero, or its ROC AUC by more than 0.05, or its low-band share ratio falls below 0.8. This is a disparity report, not a fairness certification, and the report says so.
14. **No new dependency.** scikit-learn, LightGBM, numpy, and duckdb are already `bank-ml` dependencies.
15. **ADR number.** The prompt names 0023, which is taken; the record is ADR 0030.

## Files to create or change

| Path | Change |
|---|---|
| `services/api/src/bank_agent/adapters/models/risk_features.py` | Shared feature vector from `CreditRiskFeatures` or `CreditProfile` |
| `services/api/src/bank_agent/adapters/models/learned_risk.py` | `risk_classifier/1` artifact model and `LearnedRiskEstimator` (`logreg`, `lgbm`) |
| `services/api/src/bank_agent/bootstrap/{models,workflows,settings}.py` | `build_risk_estimator`, selection pattern, fallback |
| `ml/src/bank_ml/common/leakage.py` | Risk label denylist, protected attributes, name scan |
| `ml/src/bank_ml/risk/` | `data.py`, `guards.py`, `models.py`, `calibration.py`, `uncertainty.py`, `scoring.py`, `evaluate.py`, `slices.py`, `pipeline.py`, `promotion.py`, `report.py`, `command.py` |
| `ml/src/bank_ml/cli.py`, `Makefile` | `bank-ml risk train`, `evaluate`, and `promote`; `make train` and `make promote` |
| Docs | `docs/models/risk-estimator.md`, generated `docs/evaluation/risk-estimator.md`, ADR 0030, `ml/README.md`, `credit-separation.md`, `credit-information.md`, `eligibility.md` (note only), BACKLOG, PROGRESS |

## Tests to add

- Unit (ml): label construction with one snapshot and, through a pure function, with two snapshots (label strictly after features at a horizon); the protected-attribute and leakage guards; split determinism and isolation; the calibrators; Venn-Abers on a synthetic distribution; the bootstrap and group coverage; band assignment including the borderline case against the pack cut points; metric functions against scikit-learn.
- Unit (api): the artifact validation, band and flag logic, `missing_features`, `out_of_distribution`, and interval clipping; the bootstrap selection and fallback; the contract suite with the score-band, `logreg`, and `lgbm` adapters over fixture artifacts.
- Integration (ml): train on a synthetic gold fixture end to end, evaluate, promote, load through the `bank_agent` adapter and predict, equality of the numpy scorer and the adapter to 1e-9, and the reproducibility test (identical versions and metrics on retraining).
- Existing credit scenarios, the separation test, and the property keep passing unchanged. The separation test also runs with a learned estimator.

## Risks

- The learned model's signal is structural (more credit products, more chances of a delinquent one); the report must not present it as creditworthiness. Credit score shows no association with the label, so the synthetic eligibility score minimums find no support in this label. That is a finding for pending action 17, not a change to the policy.
- The estimate matters little in the flow: the eligibility service already sends any customer with days past due above zero to review, so the estimate is read only for customers whose own label is negative. The model card states this.
- Artifact size and startup time with a 20-member bootstrap ensemble; kept small by shallow trees.
- `make check` time; long suites run in the background with logs.
