---
clause_id: SCOPE-ALL-1
version: 1
jurisdiction: ALL
language: es
effective_from: 2026-09-27
synthetic: true
params:
  supported_workflows: [account_inquiry, card_support, dispute, credit]
bound_rules: [SCOPE.workflow_supported, SCOPE.supported_intent, SCOPE.action_allowed_in_state]
summary: Qué puede hacer el asistente y con qué política sintética de demostración opera.
---
Este asistente opera con una política sintética de demostración, no con condiciones reales de un banco. Puede ayudarte con consultas de saldos, pagos y resúmenes de cuenta; con el estado de tus tarjetas y el bloqueo preventivo de una tarjeta; con la presentación y el seguimiento de una reclamación por una transacción; y con información sobre productos de crédito y una orientación indicativa sobre elegibilidad. Solo realiza las acciones que esta política permite, siempre con tu confirmación, y te informa únicamente de los resultados que pudo verificar.
