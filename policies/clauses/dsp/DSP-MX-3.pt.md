---
clause_id: DSP-MX-3
version: 2
jurisdiction: MX
language: pt
effective_from: 2026-09-27
synthetic: true
params:
  auto_intake_max_amount: {amount: "10000.00", currency: MXN}
  usd_exchange_rate: {amount: "18.50", currency: MXN}
  usd_exchange_rate_as_of: "2026-06-17"
  usd_exchange_rate_source: "synthetic team-set rate; the organizer sample has no MXN rate"
bound_rules: [DSP.amount_within_auto_limit]
summary: Valor máximo sintético para registrar uma contestação automaticamente no México.
---
O assistente pode registrar contestações de valores até {auto_intake_max_amount}. Se o valor for maior, uma pessoa da equipe assume o seu caso desde o início para analisá-lo com você.
