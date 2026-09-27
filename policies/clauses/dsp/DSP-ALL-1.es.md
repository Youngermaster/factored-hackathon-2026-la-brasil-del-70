---
clause_id: DSP-ALL-1
version: 1
jurisdiction: ALL
language: es
effective_from: 2026-09-27
synthetic: true
params:
  eligible_statuses: [approved]
bound_rules: [DSP.status_eligible]
summary: Qué transacciones se pueden reclamar según su estado.
---
Solo se pueden reclamar transacciones aplicadas. Una transacción pendiente todavía puede cambiar, así que te pediremos esperar a que se aplique. Una transacción rechazada o revertida no generó un cargo definitivo, por lo que no hay nada que reclamar.
