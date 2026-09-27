---
clause_id: ESC-ALL-1
version: 1
jurisdiction: ALL
language: pt
effective_from: 2026-09-27
synthetic: true
params:
  repeat_complaint_threshold: 3
  repeat_complaint_lookback_days: 180
  clarification_budget: 2
  tool_retry_budget: 2
bound_rules: [ESC.human_requested, ESC.legal_or_regulator_mention, ESC.clarification_exhausted, ESC.tool_failure_exhausted, ESC.verification_mismatch, ESC.repeat_complainer, ESC.risk_tier_high]
summary: Quando a conversa passa para uma pessoa da equipe.
---
Uma pessoa da equipe assume a conversa quando você pede; quando você menciona uma ação judicial ou um órgão regulador; quando você já registrou {repeat_complaint_threshold} ou mais reclamações nos últimos {repeat_complaint_lookback_days} dias; quando, depois de {clarification_budget} perguntas, ainda não conseguimos entender a sua solicitação; quando um sistema falha depois de {tool_retry_budget} novas tentativas; quando o resultado de uma ação não confere com o esperado; ou quando detectamos sinais de risco na sessão. A pessoa recebe um resumo da solicitação, os dados verificados e as ações realizadas, para que você não precise repetir tudo.
