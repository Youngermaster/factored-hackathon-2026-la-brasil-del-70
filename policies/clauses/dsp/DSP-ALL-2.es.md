---
clause_id: DSP-ALL-2
version: 1
jurisdiction: ALL
language: es
effective_from: 2026-09-27
synthetic: true
params:
  required_fields: [transaction, reason, disputed_amount]
bound_rules: [DSP.required_fields_present]
summary: Información necesaria para registrar una reclamación.
---
Para registrar una reclamación necesitamos identificar la transacción contigo, el motivo y el monto que reclamas, que no puede superar el monto de la transacción. Si hay varias transacciones parecidas, te mostraremos las opciones para que elijas la correcta; nunca la elegimos por ti.
