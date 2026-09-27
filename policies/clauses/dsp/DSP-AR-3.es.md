---
clause_id: DSP-AR-3
version: 1
jurisdiction: AR
language: es
effective_from: 2026-09-27
synthetic: true
params:
  auto_intake_max_amount: {amount: "600000.00", currency: ARS}
bound_rules: [DSP.amount_within_auto_limit]
summary: Monto máximo sintético para registrar un desconocimiento de forma automática en Argentina.
---
El asistente puede registrar desconocimientos por montos de hasta {auto_intake_max_amount}. Si el monto es mayor, una persona del equipo toma tu caso desde el inicio para revisarlo con vos.
