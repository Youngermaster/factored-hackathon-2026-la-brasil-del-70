---
clause_id: ELG-AR-1.2
version: 1
jurisdiction: AR
language: pt
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
summary: Regras sintéticas de elegibilidade para empréstimo pessoal na Argentina.
---
Regras sintéticas de demonstração para empréstimo pessoal na Argentina. A orientação é favorável quando a sua pontuação de crédito é de pelo menos {min_credit_score}; a parcela mensal estimada à taxa máxima do produto não passa de {max_payment_to_income_pct} % da sua renda mensal; você não tem dias de atraso nos seus produtos de crédito; você é cliente há pelo menos {min_tenure_months} meses; a estimativa de risco sintética está em uma faixa baixa; e o valor está dentro da faixa do produto. Se o valor passar de {review_amount_threshold}, ou se houver algum atraso, uma pessoa da equipe analisa o caso. Estas regras não são uma política real de crédito e não tomam nenhuma decisão.
