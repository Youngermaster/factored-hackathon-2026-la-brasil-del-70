---
clause_id: ELG-CO-1.2
version: 1
jurisdiction: CO
language: en
effective_from: 2026-09-27
synthetic: true
params:
  product_type: personal_loan
  min_credit_score: 660
  max_payment_to_income_pct: 40
  max_days_past_due: 0
  min_tenure_months: 12
  acceptable_risk_bands: [low, medium]
  review_amount_threshold: {amount: "50000000.00", currency: COP}
bound_rules: [ELG.credit_score_minimum, ELG.payment_to_income_max, ELG.days_past_due_max, ELG.tenure_minimum, ELG.amount_within_product_range, ELG.risk_band_acceptable]
summary: Synthetic eligibility rules for a personal loan in Colombia.
---
Synthetic demonstration rules for a personal loan in Colombia. The guide is favorable when your credit score is at least {min_credit_score}; the estimated monthly installment at the product's maximum rate is no more than {max_payment_to_income_pct} % of your monthly income; you have no days past due on your credit products; you have been a customer for at least {min_tenure_months} months; the synthetic risk estimate is in a low or medium band; and the amount is within the product's range. If the amount exceeds {review_amount_threshold}, or if there are any arrears, a person from the team reviews the case. These rules are not a real credit policy and make no decision.
