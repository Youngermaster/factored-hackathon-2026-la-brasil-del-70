---
clause_id: ACC-ALL-2
version: 1
jurisdiction: ALL
language: es
effective_from: 2026-09-27
synthetic: true
params:
  max_statement_days: 92
bound_rules: [ACC.statement_period_within_limit]
summary: Período máximo de un resumen de movimientos.
---
Podemos preparar un resumen de movimientos de un producto para un período de hasta {max_statement_days} días. El resumen muestra los totales por moneda de las operaciones aplicadas e indica aparte las operaciones pendientes, rechazadas o revertidas y las que no se pueden clasificar como cargo o abono.
