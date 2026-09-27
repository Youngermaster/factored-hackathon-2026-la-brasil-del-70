---
clause_id: ELG-MX-1.1
version: 1
jurisdiction: MX
language: pt
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
summary: Regras sintéticas de elegibilidade para cartão de crédito no México.
---
Regras sintéticas de demonstração para cartão de crédito no México. A orientação é favorável quando a sua pontuação de crédito é de pelo menos {min_credit_score}; o pagamento mensal estimado, de {card_payment_pct_of_limit} % do limite pedido, não passa de {max_payment_to_income_pct} % da sua renda mensal; você não tem dias de atraso nos seus produtos de crédito; você é cliente há pelo menos {min_tenure_months} meses; a estimativa de risco sintética está em uma faixa baixa ou média; e o valor está dentro da faixa do produto. Se o valor passar de {review_amount_threshold}, ou se houver algum atraso, uma pessoa da equipe analisa o caso. Estas regras não são uma política real de crédito e não tomam nenhuma decisão.
