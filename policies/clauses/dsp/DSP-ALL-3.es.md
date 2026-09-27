---
clause_id: DSP-ALL-3
version: 1
jurisdiction: ALL
language: es
effective_from: 2026-09-27
synthetic: true
params:
  supported_reasons: [unrecognized, duplicate, wrong_amount, not_received, atm_cash_not_dispensed, subscription_cancelled]
bound_rules: [DSP.reason_supported]
summary: Motivos de reclamación que el asistente puede registrar.
---
El asistente puede registrar reclamaciones por estos motivos: una transacción que no reconoces, un cargo duplicado, un monto distinto al acordado, un producto o servicio que no recibiste, un retiro en cajero en el que no se entregó el efectivo y un cobro de una suscripción que ya cancelaste. Cualquier otro motivo lo revisa una persona del equipo.
