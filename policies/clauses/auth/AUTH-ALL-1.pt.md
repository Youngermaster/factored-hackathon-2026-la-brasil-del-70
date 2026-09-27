---
clause_id: AUTH-ALL-1
version: 1
jurisdiction: ALL
language: pt
effective_from: 2026-09-27
synthetic: true
params:
  step_up_window_minutes: 5
  session_idle_minutes: 15
  elevated_risk_required_level: step_up
bound_rules: [AUTH.session_valid, AUTH.required_level, AUTH.step_up_valid]
summary: Verificação de identidade exigida para consultar dados e para cada ação.
---
Para consultar informações dos seus produtos, você precisa de uma sessão verificada com um código de uso único enviado ao seu telefone cadastrado. Para qualquer ação, como bloquear um cartão, abrir uma contestação ou registrar uma solicitação de crédito, pediremos também uma verificação reforçada com um novo código, válida por {step_up_window_minutes} minutos. A sessão é encerrada após {session_idle_minutes} minutos sem atividade.

Se detectarmos sinais de risco na conversa, poderemos pedir a verificação reforçada também antes de mostrar informações.
