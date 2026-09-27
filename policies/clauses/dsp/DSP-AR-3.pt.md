---
clause_id: DSP-AR-3
version: 1
jurisdiction: AR
language: pt
effective_from: 2026-09-27
synthetic: true
params:
  auto_intake_max_amount: {amount: "600000.00", currency: ARS}
bound_rules: [DSP.amount_within_auto_limit]
summary: Valor máximo sintético para registrar uma contestação automaticamente na Argentina.
---
O assistente pode registrar contestações de valores até {auto_intake_max_amount}. Se o valor for maior, uma pessoa da equipe assume o seu caso desde o início para analisá-lo com você.
