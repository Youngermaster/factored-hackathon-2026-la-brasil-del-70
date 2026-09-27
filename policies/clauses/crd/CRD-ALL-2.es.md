---
clause_id: CRD-ALL-2
version: 1
jurisdiction: ALL
language: es
effective_from: 2026-09-27
synthetic: true
params:
  block_requires_step_up: true
  step_up_window_minutes: 5
bound_rules: [CRD.card_active, CRD.block_requires_step_up]
summary: Bloqueo preventivo de una tarjeta, verificación reforzada y consecuencias.
---
Puedes bloquear de forma preventiva una tarjeta activa si la perdiste, te la robaron o ves movimientos que no reconoces. Antes de bloquearla te pediremos una verificación reforzada, válida durante {step_up_window_minutes} minutos, y tu confirmación expresa.

El bloqueo es inmediato: la tarjeta deja de funcionar para compras, retiros y cargos recurrentes, y los pagos automáticos asociados pueden fallar. El asistente no puede desbloquearla ni emitir una tarjeta nueva; esas solicitudes las atiende una persona del equipo. Solo te confirmaremos el bloqueo después de comprobar en los registros que la tarjeta quedó bloqueada.
