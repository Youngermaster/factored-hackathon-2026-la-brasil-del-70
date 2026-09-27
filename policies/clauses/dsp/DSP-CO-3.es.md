---
clause_id: DSP-CO-3
version: 1
jurisdiction: CO
language: es
effective_from: 2026-09-27
synthetic: true
params:
  auto_intake_max_amount: {amount: "2000000.00", currency: COP}
bound_rules: [DSP.amount_within_auto_limit]
summary: Monto máximo sintético para registrar una reclamación de forma automática en Colombia.
---
El asistente puede registrar reclamaciones por montos de hasta {auto_intake_max_amount}. Si el monto es mayor, una persona del equipo toma tu caso desde el inicio para revisarlo contigo.
