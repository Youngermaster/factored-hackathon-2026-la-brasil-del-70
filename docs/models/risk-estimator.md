# Model card: credit risk estimator (snapshot risk estimate)

This is a risk estimate trained on synthetic organizer data. It is not a lending model, it is not validated for any real credit decision, and it never approves or declines anything. It is one input to the synthetic eligibility service (phase 06), which is also labeled synthetic.

**Label definition** (`label_definition` = `snapshot_dpd30_any_credit_product`): any open credit product (credit card, personal loan, or mortgage) is 30 or more days past due at the snapshot date. **The estimate is cross-sectional, not forward-looking.** The delivery has one snapshot of customers and products, so the label is observed at the same instant as the features. The estimate measures a concurrent association between a profile and current delinquency. It is not a forecast and not a default prediction.

| Field | Value |
|---|---|
| Component | `RiskEstimator` port (`bank_agent.ports.models`) |
| Implementations | `risk_estimator:logreg` (champion `2afb401aa70e`); `risk_estimator:lgbm` (candidate `1c54c935b495`, promotion refused); baseline `risk_estimator:score_band@1` (served by default) |
| Owner | ml |
| Trained by | `make train` (`bank-ml risk train`); evaluated by `bank-ml risk evaluate`; promoted by `make promote APPROVED_BY=...` |
| Full results | [`docs/evaluation/risk-estimator.md`](../evaluation/risk-estimator.md) (generated) |
| Decision record | [ADR 0030](../adr/0030-credit-risk-estimator.md) |

## Intended use

The estimate is internal. The credit workflow's ESTIMATE_RISK state calls it with the `CreditRiskFeatures` allowlist, and it returns a calibrated probability, an interval, a band, and flags. The synthetic eligibility service reads the band and the interval: an interval that reaches a cut point, widened by the margin, is borderline and goes to human review. It never reads the probability alone. The estimate is recorded in `ExecutionRecord.risk_estimates` and shown to agents in the handoff's credit review. It is never shown to customers and never sent to a language model ([credit separation](../architecture/credit-separation.md)).

Out of scope: any real credit decision, pricing, limits, or collections; any customer-facing use; any population other than customers who already hold an open credit product.

## Data

- **Source.** Gold `credit_profiles_serving` (features), `products_serving` (label), and `customers_serving` (slices only). The features come from the table the API's `CreditProfile` reader serves, and training and serving build the vector with one shared function (`bank_agent.adapters.models.risk_features`), so they cannot drift apart.
- **Population.** 77,229 customers with at least one open credit product and a known days-past-due value on every one of them:
  - 2,784 customers with no known value are excluded;
  - 3,178 customers with a partly unknown value are excluded, so an unknown product cannot hide a positive.
- **Label distribution.** 17.1% positive overall: train 7,848 of 46,264, dev 2,690 of 15,643, test 2,645 of 15,322.
- **What the data shows.**
  - Delinquency is about 12.4% per credit product, whatever the product type or status.
  - The customer rate follows the credit product count (1: 12.8%, 2: 23.7%, 3: 34.3% on test), which is what independent per-product delinquency gives.
  - Credit score, income, tenure, and utilization show no association with the label (univariate ROC AUC 0.495 to 0.502).
  - Country, segment, gender, occupation, education, and marital status rates are all between 16% and 18%.

## Features and exclusions

| Feature | Source | Notes |
|---|---|---|
| `credit_score` | profile | Monotone decreasing constraint in LightGBM |
| `tenure_months` | profile | |
| `credit_product_count` | profile | Open credit products; the only feature with signal |
| `utilization` | profile | Revolving card utilization; missing without a card |

Excluded, with the reason:

- `max_days_past_due`: it defines the label (leakage). The eligibility service still reads it directly as its own policy rule (`ELG.days_past_due_max`), which is policy, not the model.
- `product_type`, `requested_term_months`, `requested_amount_to_income`: they describe an application, and the snapshot has none, so the estimate is customer-level, not product-specific.
- `monthly_income_usd`: the application never sets it (no exchange rates are wired), so training on it would create a training-serving skew; income shows no association.
- `jurisdiction`: a slice, not a feature; rates are equal across countries.
- Protected and proxy attributes and identifiers are never read as features: gender, date of birth and age, marital status, detected accent, city, state, postal code, address, segment (an age proxy through `student`), occupation, education level, names, contact details, and every identifier. Segment and country are read only by the slice reader.
- The guard `assert_risk_features_clean` (`bank_ml.common.leakage`) refuses any feature column that is post-outcome, label-derived (any `days_past_due` column, customer and product statuses from the same snapshot), protected, or an identifier. A unit test scans the source of every feature module for these names, including attributes and keyword arguments.

## Splits

Customers are split by a salted hash: 60% train, 20% dev, 20% test, so no customer appears in two splits. There is no temporal split, because there is one snapshot. Dev is halved by a second hash:

- **calibration half** (7,799): early stopping, calibrator fits, Venn-Abers counts;
- **selection half** (7,844): calibrator and interval choices, and dev metrics.

Test (15,322) was scored once by `evaluate`, after every choice was frozen.

## Models

| Model | Description |
|---|---|
| `score_band@1` | The phase 09 baseline: fixed prior probabilities per credit score band |
| Score bands re-estimated | The same bands with the observed train rate per band (evaluation only) |
| `logreg` | Median imputation, one missing indicator per feature, standardization, L2 logistic regression (C = 1.0) |
| `lgbm` | Binary LightGBM (7 leaves, 200 minimum rows per leaf, learning rate 0.1, 33 rounds by early stopping on the calibration half), seeded, one thread, deterministic, monotone decreasing in credit score |

Both learned models are exported as `risk_classifier/1` JSON artifacts (parameters only) and served in pure Python by `LearnedRiskEstimator`. Numpy scoring and the serving adapter agree to 1e-9 on a sample, and LightGBM's own raw scores are checked at export.

## Calibration, intervals, and bands

- **Calibration.** Identity (the model's own sigmoid), Platt, and isotonic maps were fitted on the calibration half and chosen by selection log loss. Identity won for both models (logreg 0.4394, lgbm 0.4385).
- **Intervals.** Two methods were compared on the selection half:
  - a bootstrap ensemble: 20 members refit on train bootstraps and recalibrated on calibration-half bootstraps; 2.5% to 97.5% percentiles;
  - binned inductive Venn-Abers: the conformal-family predictor for probabilities. Plain split conformal gives label sets for a binary outcome, not a probability interval.

  Both reached the pre-registered group coverage (1.00). The narrower one was chosen: the bootstrap for logreg (mean width 0.0145) and Venn-Abers for lgbm (0.0087). On test, group coverage is 1.00 for both. The stricter share of groups whose observed rate lies inside the mean interval is 0.40 and 0.20: the intervals describe estimation uncertainty, which is small with 46,000 training customers, not the noise of a group's observed rate.
- **Bands.** The cut points come from the policy (`ELG-ALL-2`: 0.20 and 0.35, margin 0.01), read from the pack at training time and stored in the artifact.

  | Model | Low | Medium | High | Borderline |
  |---|---|---|---|---|
  | `logreg` | 67.0% | 31.5% | 1.5% | 22.2% |
  | `lgbm` | 67.0% | 31.4% | 1.6% | 2.6% |

  Borderline differs because logreg estimates two-product customers at about 0.215, close to the 0.20 cut.
- **Flags.**
  - `missing_features`: 34.5% of test customers, mostly a missing utilization for customers without a card; the band stands.
  - `out_of_distribution`: a feature outside the train range; the band becomes `unknown`, so the eligibility service asks for review. Every first-time applicant has zero credit products and is out of the population, so this flag applies to all of them.
  - `wide_interval`: an interval wider than 0.10 (lgbm 0.6%, logreg 0.0%).

## Metrics (test split, 15,322 customers, 2,645 positive; 95% customer bootstrap intervals)

| Model | ROC AUC | PR AUC | Brier | ECE |
|---|---|---|---|---|
| `score_band@1` | 0.504 [0.492, 0.514] | 0.174 [0.167, 0.182] | 0.1935 | 0.1938 |
| Score bands re-estimated | 0.505 [0.493, 0.517] | 0.174 [0.167, 0.182] | 0.1428 | 0.0031 |
| `logreg` | 0.611 [0.599, 0.623] | 0.258 [0.246, 0.273] | 0.1383 | 0.0078 |
| `lgbm` | 0.612 [0.599, 0.624] | 0.257 [0.243, 0.272] | 0.1380 | 0.0039 |

Paired differences, from the same resampled customers:

- `logreg` against the shipped score bands: ROC AUC +0.107 [+0.093, +0.124].
- `lgbm` against `logreg`: ROC AUC +0.001 [-0.005, +0.007], PR AUC -0.001 [-0.006, +0.004].

**Promotion** (rule fixed in the plan before any test number existed):

- `logreg` beats both score-band baselines on every condition and was promoted.
- `lgbm` beats the score-band baselines but not `logreg`, so its promotion was refused.
- The approver is recorded as "orchestrator (human-delegated approval, session 10b)".
- LightGBM's only measurable advantage is calibration by credit product count, where logreg over-estimates customers with four or more products (0.514 against an observed 0.389, 229 customers).

## Slices and disparities

This is a disparity report for investigation, not a fairness certification. By country (AR 3,051, CO 4,622, MX 7,649), segment (basic 9,085, plus 3,895, premium 1,580, student 762), and within-country income tertile, both learned models show:

- calibration gaps from -0.010 to +0.005, none different from the rest of the population;
- ROC AUC between 0.595 and 0.624;
- low-band shares between 65.5% and 69.7%.

No population group crosses a threshold (calibration gap difference above 0.02 with an interval excluding zero, ROC AUC difference above 0.05, or a low-band share ratio below 0.8). The credit product count slice is diagnostic, because it is the main feature: within each count, ROC AUC is about 0.5, so the models separate customers only by how many credit products they hold.

## Limitations

- **Cross-sectional, synthetic, and weak.** The label is concurrent, the data is synthetic, and the only signal is structural: more credit products give more chances that one is delinquent. The estimate says nothing about creditworthiness. Credit score carries no association with this label, so the synthetic eligibility score minimums find no support in it (pending action 17).
- **Little effect in the flow.** The eligibility service already sends any customer with days past due above zero to review. The estimate is therefore read only for customers whose own label is negative, where it describes customers with a similar profile.
- **First-time applicants.** Customers with no credit product are outside the training population and always get an `unknown` band, and therefore review, with a learned estimator.
- **Not product-specific.** The estimate does not depend on the requested product, term, or amount.
- **Group coverage is lenient.** The interval criterion passes easily; the stricter inside share is reported next to it.
- **Default stays the baseline.** The API serves `score_band@1` until phase 14 runs the scenario and evaluation sets with `WORKFLOW_RISK_ESTIMATOR=logreg@champion` (BACKLOG).

## Ethical considerations

The estimator never approves or declines anything and has no approved outcome. Protected and proxy attributes are excluded from the features by construction, a guard, and a source scan. Segment and country are used only to look for disparities, and none was found above the documented thresholds; that is not a certification. Everything is labeled synthetic (`synthetic_data` on every estimate). The estimate stays internal: the prompt registry refuses any risk field as a prompt input, and customer views have no field for it. Error examples in the generated report coarsen the synthetic feature values and carry no identifier.
