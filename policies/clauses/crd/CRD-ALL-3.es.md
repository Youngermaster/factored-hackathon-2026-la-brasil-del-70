---
clause_id: CRD-ALL-3
version: 1
jurisdiction: ALL
language: es
effective_from: 2026-09-27
synthetic: true
params:
  handoff_sla_hours: 24
bound_rules: [CRD.unblock_requires_human, CRD.replacement_requires_human]
summary: El desbloqueo y la reposición de una tarjeta los atiende una persona.
---
El desbloqueo de una tarjeta y la emisión de una tarjeta de reposición requieren verificaciones de identidad y de fraude que el asistente no puede realizar. Por eso trasladamos tu solicitud a una persona del equipo, con el detalle de lo que pediste y de la tarjeta, para que te contacte dentro de las {handoff_sla_hours} horas siguientes. Mientras tanto, la tarjeta sigue en su estado actual.
