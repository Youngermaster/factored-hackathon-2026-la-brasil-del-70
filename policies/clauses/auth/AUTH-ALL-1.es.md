---
clause_id: AUTH-ALL-1
version: 1
jurisdiction: ALL
language: es
effective_from: 2026-09-27
synthetic: true
params:
  step_up_window_minutes: 5
  session_idle_minutes: 15
  elevated_risk_required_level: step_up
bound_rules: [AUTH.session_valid, AUTH.required_level, AUTH.step_up_valid]
summary: Verificación de identidad requerida para consultar datos y para cada acción.
---
Para consultar información de tus productos necesitas una sesión verificada con un código de un solo uso enviado a tu teléfono registrado. Para cualquier acción, como bloquear una tarjeta, presentar una reclamación o registrar una solicitud de crédito, te pediremos además una verificación reforzada con un nuevo código, válida durante {step_up_window_minutes} minutos. La sesión se cierra tras {session_idle_minutes} minutos sin actividad.

Si detectamos señales de riesgo en la conversación, podemos pedirte la verificación reforzada también antes de mostrarte información.
