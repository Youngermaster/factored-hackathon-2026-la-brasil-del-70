# Synthetic eligibility service

**None of this is a real lending policy.** The rules, thresholds, and products below are synthetic demonstration content written by the team, plausible for Mexico, Colombia, and Argentina, and labeled synthetic in every file and every output. The service gives an indicative orientation and never approves or declines credit; a person from the credit team makes any real decision outside the prototype. It follows the separation in [ADR 0021](../adr/0021-credit-risk-and-eligibility-separation.md) and the kernel design in [ADR 0011](../adr/0011-policy-as-data-and-pure-rule-functions.md).

`SyntheticEligibilityService` (`bank_agent/policy/eligibility/service.py`) implements the `EligibilityPolicy` port. It runs the registered ELG rules with parameters from the ELG clauses of `policies/clauses/elg/` and identifies itself as `eligibility:synthetic@<pack version>`. The risk estimate is an input (band and interval from the `RiskEstimator` port); the service never computes one, never calls a model, and never returns the estimate or the credit profile in a customer-facing form.

## Rules

| Rule | Passes when | Failure |
|---|---|---|
| `ELG.self_service_product` | The product supports self-service eligibility (not a mortgage) | Review: `product_requires_human_assessment`; no other rule runs |
| `ELG.credit_score_present` | A credit score is on record | Missing fact `credit_score` |
| `ELG.credit_score_minimum` | Score at least the product minimum | Hard rule (not eligible) |
| `ELG.income_present` | A monthly income exists: the profile's estimate, else the income the customer declares, in the product currency | Missing fact `monthly_income` |
| `ELG.payment_to_income_max` | Estimated monthly payment at most the maximum share of income | Hard rule |
| `ELG.days_past_due_max` | Days past due at most the maximum (0 everywhere) | Review: `days_past_due_present`; missing fact `max_days_past_due` |
| `ELG.tenure_minimum` | Months as a customer at least the minimum | Hard rule; missing fact `tenure_months` |
| `ELG.amount_within_product_range` | Amount, term, and purpose inside the catalog entry; amount at most the review threshold | Hard rule outside the range; review above the threshold (`amount_above_review_threshold`) |
| `ELG.risk_estimate_available` | An estimate exists and its band is not `unknown` | Review: `risk_estimate_unavailable` |
| `ELG.risk_band_acceptable` | The band is in the product's acceptable bands | Hard rule |
| `ELG.risk_interval_not_borderline` | The interval, widened by the margin, stays clear of both cut points | Review: `borderline_risk_interval` |

The monthly payment of a loan is the annuity at the product's maximum annual rate over the requested term (a conservative estimate); for a card it is a clause percentage of the requested limit. Bounds are inclusive. The borderline test is strict: an interval from `low` to `high` is borderline when `low < cut + margin` and `high > cut - margin` for either cut point.

## Parameters per jurisdiction and product

Common to all (`ELG-ALL-2`): band cut points at 0.20 (low to medium) and 0.35 (medium to high) estimated probability, margin 0.01.

| Clause | Product | Min score | Max payment / income | Card payment | Max days past due | Min tenure | Acceptable bands | Review above |
|---|---|---|---|---|---|---|---|---|
| `ELG-MX-1.1` | Credit card | 620 | 30% | 5% of the limit | 0 | 6 months | low, medium | 80,000 MXN |
| `ELG-MX-1.2` | Personal loan | 650 | 35% | | 0 | 12 months | low, medium | 200,000 MXN |
| `ELG-CO-1.1` | Credit card | 630 | 30% | 5% of the limit | 0 | 6 months | low, medium | 15,000,000 COP |
| `ELG-CO-1.2` | Personal loan | 660 | 40% | | 0 | 12 months | low, medium | 50,000,000 COP |
| `ELG-AR-1.1` | Credit card | 600 | 25% | 6% of the limit | 0 | 6 months | low, medium | 5,000,000 ARS |
| `ELG-AR-1.2` | Personal loan | 650 | 30% | | 0 | 18 months | low | 15,000,000 ARS |

Mortgages (`MX-MG-FIXED`, `CO-MG-FIXED`, `AR-MG-UVA`) are information only: `ELG-ALL-3` sends every mortgage to a human, because collateral facts are not in the data. The product ranges are in the [policy catalog](catalog.md#credit-catalog). The demo persona band for a borderline score (640 to 660, `data_platform/src/bank_data/seed/criteria.py`) brackets the Argentine personal loan minimum of 650.

## Outcome mapping

The mapping is deterministic, and the first matching line wins:

| Order | Condition | Outcome | Review reasons |
|---|---|---|---|
| 1 | The product has no self-service eligibility | `review_required` | `product_requires_human_assessment` |
| 2 | Any rule reports a missing fact | `insufficient_data` | `missing_credit_score`, `missing_income` when those facts are missing |
| 3 | Any rule asks for review | `review_required` | `risk_estimate_unavailable`, `borderline_risk_interval`, `days_past_due_present`, `amount_above_review_threshold` |
| 4 | Any other rule failed | `not_eligible` | none |
| 5 | Every rule passed | `indicatively_eligible` | none |

Review ranks above a failed hard rule so that any uncertainty reaches a person. Hypothesis properties check that the service never returns `indicatively_eligible` with a missing fact, a missing estimate, or an interval that straddles a cut point, and that a worse band never improves the outcome.

## What the customer sees

`EligibilityView` (outcome, reasons with clause citations, missing facts, uncertainty statement, review path, disclaimer) is rendered by `render_eligibility` from `policies/messages/eligibility.<lang>.yaml` and the `CRE-ALL-1` disclaimer, in es, pt, or en. The text opens with a synthetic notice, lists each reason once with the clauses that cite it, and never contains approval wording in any language, even negated: the renderer refuses such text and a test checks every message and credit clause. Review paths: submit an application intake for human review (indicatively eligible), ask for a person (review or not eligible), or provide the missing information (insufficient data).

## Limitations

- The thresholds are invented and unvalidated; they are not calibrated to any portfolio.
- The estimator is a placeholder until phases 09 and 10; with no estimate every self-service request goes to review.
- Declared income is taken at face value for the indication; a human verifies it on review.
- The thresholds and the catalog await a separate human review (recorded in `docs/PROGRESS.md`).
