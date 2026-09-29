# 0030: Credit risk estimator: label, features, uncertainty, and separation from eligibility policy

- Status: accepted
- Date: 2026-09-27

The phase 10 prompt names this record 0023, which was already taken; it is 0030.

## Context

The brief keeps predictive risk estimates apart from eligibility policy ([ADR 0021](0021-credit-risk-and-eligibility-separation.md)). The `RiskEstimator` port has been served by `risk_estimator:score_band@1`, a fixed-prior baseline with no trained label. The prompt asks for a learned estimator with a documented label, leakage and protected-attribute guards, calibration, an interval per estimate, bands, a disparity report, and adapters loaded through `ModelRegistry`.

Four facts from the data shape the decision:

- The delivery has **one snapshot** of customers and products, so no label can follow its features in time.
- Days past due exist only on credit products. About 12.4% of credit products are 30 or more days past due, with no dependence on product type or status.
- On the 80,407 customers with a known value, credit score, income, tenure, and utilization show no association with "any credit product 30 or more days past due" (ROC AUC 0.495 to 0.502). The credit product count does (0.615), and the customer rate follows `1 - (1 - 0.124)^k`.
- The API image carries no ML library, and the eligibility service reads the band and the interval, with cut points 0.20 and 0.35 in `ELG-ALL-2`.

## Considered options

Label:

1. **A forward-looking label** (features at t, outcome at t plus a horizon). Impossible with one snapshot.
2. **A proxy outcome from other tables** (complaints about fees, declined payments). These are unrelated to credit delinquency and mostly noise.
3. **A cross-sectional delinquency label** at the snapshot, with every column derived from days past due excluded from the features, stated as a concurrent association.

Features:

1. **Every `CreditRiskFeatures` field**, including days past due and the application fields. This leaks the label, and the application fields do not exist in the snapshot.
2. **The allowlisted fields served at inference exactly as in training**: credit score, tenure, credit product count, and utilization.

Uncertainty:

1. **Split conformal prediction.** For a binary outcome it gives label sets, not a probability interval, so it does not fit the band test.
2. **A bootstrap ensemble.** Members refit on train bootstraps and recalibrated on dev bootstraps.
3. **Binned inductive Venn-Abers**, the conformal-family predictor that outputs a probability interval.

## Decision

- **Label.** Cross-sectional option 3, `snapshot_dpd30_any_credit_product`: any open credit product 30 or more days past due. The population is customers with an open credit product whose values are all known. `bank_ml.risk.labels` also implements the forward-looking mode, and refuses an outcome that is not strictly later, so a delivery with monthly snapshots changes the configuration, not the code. Every artifact carries the label definition, and every report calls the estimate a snapshot risk estimate, not a forecast.
- **Features.** Option 2, read from gold `credit_profiles_serving` (the table the API serves) through one shared feature function. Days past due, customer and product statuses, protected and proxy attributes, and identifiers are refused by a guard (`assert_risk_features_clean`) and by a source scan in the unit tests. Segment and country are evaluation slices only.
- **Models.**
  - Baselines: `score_band@1` as shipped, the same bands re-estimated on train, and logistic regression.
  - Candidate: LightGBM with a monotone decreasing constraint on the credit score.
  - Both learned models are exported as `risk_classifier/1` JSON and served in pure Python (`risk_estimator:logreg`, `risk_estimator:lgbm`).
- **Calibration and uncertainty.** The calibrator (identity, Platt, isotonic) is chosen by dev log loss. Both interval methods are computed, and the narrower one that meets the pre-registered group coverage on dev is kept per model: the bootstrap for logreg and Venn-Abers for lgbm. Test coverage is reported.
- **Bands.** Bands use the policy's cut points, read from the pack at training time. The model does not choose its own cut points, so the estimator and the eligibility service cannot disagree about what "medium" means.
- **Flags.** `out_of_distribution` makes the band `unknown`, so the eligibility service asks for review instead of trusting an extrapolation.
- **Promotion.** The human's instruction was that LightGBM must beat the baselines on the held-out test split or the champion stays the baseline. Against every reference, the rule requires a paired bootstrap lower bound of the ROC AUC difference above zero, PR AUC not lower, Brier no worse than 0.002, and ECE at most 0.03.
- **Results** (test, 15,322 customers):
  - `logreg` reached ROC AUC 0.611 against 0.504 for the shipped bands and was promoted;
  - `lgbm` reached 0.612 but did not beat `logreg` (difference +0.001 [-0.005, +0.007]), so its promotion was refused.
- **Serving.** `WORKFLOW_RISK_ESTIMATOR` selects `score_band@1` (the default), `logreg@...`, or `lgbm@...`:
  - a missing artifact serves the baseline;
  - a corrupt artifact stops startup;
  - a scoring failure raises `risk_estimator_unavailable`, never a default estimate.
- **Why it stays separate from eligibility policy.** The estimator predicts and the policy decides. The estimate is one input among the `ELG` rules (score minimums, payment to income, days past due, tenure, amount review thresholds), read only as a band and an interval. Its weakness here, a signal that is only the product count, is exactly why it must never become the decision. Keeping it behind its own port lets the team replace it, or keep the baseline, without touching policy, workflows, or prompts.

## Consequences

- The learned estimate is measured, calibrated, and honest about what it measures, but it is weak and structural. The default stays on the baseline until phase 14 runs the scenario and evaluation sets with `logreg@champion` (BACKLOG).
- With a learned estimator selected, every first-time applicant (zero credit products) is out of distribution and goes to review.
- The finding that credit score carries no association with the label goes to the review of the synthetic eligibility thresholds (pending action 17). It changes no policy by itself.
- The disparity report lists no group by country, segment, or income band. It is a report for investigation, not a fairness certification.
- A future delivery with monthly snapshots should switch the label to the forward-looking mode, rerun `make train`, and supersede this record.
