---
clause_id: ELG-ALL-2
version: 1
jurisdiction: ALL
language: pt
effective_from: 2026-09-27
synthetic: true
params:
  risk_cut_medium_bps: 2000
  risk_cut_high_bps: 3500
  borderline_margin_bps: 100
bound_rules: [ELG.risk_estimate_available, ELG.risk_interval_not_borderline]
summary: Uso da estimativa de risco sintética e da sua incerteza.
---
A orientação considera uma estimativa de risco calculada por um modelo treinado com dados sintéticos, com a sua margem de incerteza. Essa estimativa nunca é mostrada a você nem decide sozinha. Se ela não estiver disponível, ou se a sua margem ficar perto do limite entre dois níveis de risco, o resultado é que uma pessoa da equipe deve analisar o seu caso. Estas regras são sintéticas e não tomam nenhuma decisão de crédito.
