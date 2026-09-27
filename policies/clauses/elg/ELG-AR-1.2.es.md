---
clause_id: ELG-AR-1.2
version: 1
jurisdiction: AR
language: es
effective_from: 2026-09-27
synthetic: true
params:
  product_type: personal_loan
  min_credit_score: 650
  max_payment_to_income_pct: 30
  max_days_past_due: 0
  min_tenure_months: 18
  acceptable_risk_bands: [low]
  review_amount_threshold: {amount: "15000000.00", currency: ARS}
bound_rules: [ELG.credit_score_minimum, ELG.payment_to_income_max, ELG.days_past_due_max, ELG.tenure_minimum, ELG.amount_within_product_range, ELG.risk_band_acceptable]
summary: Reglas sintéticas de elegibilidad para préstamo personal en Argentina.
---
Reglas sintéticas de demostración para préstamo personal en Argentina. La orientación es favorable cuando tu puntaje de crédito es de al menos {min_credit_score}; la cuota mensual estimada a la tasa máxima del producto no supera el {max_payment_to_income_pct} % de tu ingreso mensual; no tenés días de atraso en tus productos de crédito; tenés al menos {min_tenure_months} meses como cliente; la estimación de riesgo sintética está en una banda baja; y el monto está dentro del rango del producto. Si el monto supera {review_amount_threshold}, o si tenés algún atraso, una persona del equipo revisa el caso. Estas reglas no son una política real de crédito y no toman ninguna decisión.
