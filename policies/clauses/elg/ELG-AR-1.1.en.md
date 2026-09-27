---
clause_id: ELG-AR-1.1
version: 1
jurisdiction: AR
language: en
effective_from: 2026-09-27
synthetic: true
params:
  product_type: credit_card
  min_credit_score: 600
  max_payment_to_income_pct: 25
  card_payment_pct_of_limit: 6
  max_days_past_due: 0
  min_tenure_months: 6
  acceptable_risk_bands: [low, medium]
  review_amount_threshold: {amount: "5000000.00", currency: ARS}
bound_rules: [ELG.credit_score_minimum, ELG.payment_to_income_max, ELG.days_past_due_max, ELG.tenure_minimum, ELG.amount_within_product_range, ELG.risk_band_acceptable]
summary: Synthetic eligibility rules for a credit card in Argentina.
---
Synthetic demonstration rules for a credit card in Argentina. The guide is favorable when your credit score is at least {min_credit_score}; the estimated monthly payment, {card_payment_pct_of_limit} % of the limit you ask for, is no more than {max_payment_to_income_pct} % of your monthly income; you have no days past due on your credit products; you have been a customer for at least {min_tenure_months} months; the synthetic risk estimate is in a low or medium band; and the amount is within the product's range. If the amount exceeds {review_amount_threshold}, or if there are any arrears, a person from the team reviews the case. These rules are not a real credit policy and make no decision.
