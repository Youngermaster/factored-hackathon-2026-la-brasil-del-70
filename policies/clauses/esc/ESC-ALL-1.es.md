---
clause_id: ESC-ALL-1
version: 1
jurisdiction: ALL
language: es
effective_from: 2026-09-27
synthetic: true
params:
  repeat_complaint_threshold: 3
  repeat_complaint_lookback_days: 180
  clarification_budget: 2
  tool_retry_budget: 2
bound_rules: [ESC.human_requested, ESC.legal_or_regulator_mention, ESC.clarification_exhausted, ESC.tool_failure_exhausted, ESC.verification_mismatch, ESC.repeat_complainer, ESC.risk_tier_high]
summary: Cuándo la conversación pasa a una persona del equipo.
---
Una persona del equipo toma la conversación cuando lo pides; cuando mencionas una acción legal o una autoridad; cuando ya presentaste {repeat_complaint_threshold} o más reclamos en los últimos {repeat_complaint_lookback_days} días; cuando después de {clarification_budget} preguntas todavía no logramos entender tu solicitud; cuando un sistema falla después de {tool_retry_budget} reintentos; cuando el resultado de una acción no coincide con lo esperado; o cuando detectamos señales de riesgo en la sesión. La persona recibe un resumen de tu solicitud, los datos verificados y las acciones realizadas, para que no tengas que repetirlo todo.
