---
clause_id: ELG-MX-1.1
version: 1
jurisdiction: MX
language: es
effective_from: 2026-09-27
synthetic: true
params:
  product_type: credit_card
  min_credit_score: 620
  max_payment_to_income_pct: 30
  card_payment_pct_of_limit: 5
  max_days_past_due: 0
  min_tenure_months: 6
  acceptable_risk_bands: [low, medium]
  review_amount_threshold: {amount: "80000.00", currency: MXN}
bound_rules: [ELG.credit_score_minimum, ELG.payment_to_income_max, ELG.days_past_due_max, ELG.tenure_minimum, ELG.amount_within_product_range, ELG.risk_band_acceptable]
summary: Reglas sintéticas de elegibilidad para tarjeta de crédito en México.
---
Reglas sintéticas de demostración para tarjeta de crédito en México. La orientación es favorable cuando tu puntaje de crédito es de al menos {min_credit_score}; el pago mensual estimado, del {card_payment_pct_of_limit} % del límite que pides, no supera el {max_payment_to_income_pct} % de tu ingreso mensual; no tienes días de atraso en tus productos de crédito; tienes al menos {min_tenure_months} meses como cliente; la estimación de riesgo sintética está en una banda baja o media; y el monto está dentro del rango del producto. Si el monto supera {review_amount_threshold}, o si tienes algún atraso, una persona del equipo revisa el caso. Estas reglas no son una política real de crédito y no toman ninguna decisión.
