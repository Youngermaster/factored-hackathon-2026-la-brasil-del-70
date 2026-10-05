---
clause_id: DSP-MX-3
version: 2
jurisdiction: MX
language: es
effective_from: 2026-09-27
synthetic: true
params:
  auto_intake_max_amount: {amount: "10000.00", currency: MXN}
  usd_exchange_rate: {amount: "18.50", currency: MXN}
  usd_exchange_rate_as_of: "2026-06-17"
  usd_exchange_rate_source: "synthetic team-set rate; the organizer sample has no MXN rate"
bound_rules: [DSP.amount_within_auto_limit]
summary: Monto máximo sintético para registrar una aclaración de forma automática en México.
---
El asistente puede registrar aclaraciones por montos de hasta {auto_intake_max_amount}. Si el monto es mayor, una persona del equipo toma tu caso desde el inicio para revisarlo contigo.
