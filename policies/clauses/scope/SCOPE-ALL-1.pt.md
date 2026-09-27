---
clause_id: SCOPE-ALL-1
version: 1
jurisdiction: ALL
language: pt
effective_from: 2026-09-27
synthetic: true
params:
  supported_workflows: [account_inquiry, card_support, dispute, credit]
bound_rules: [SCOPE.workflow_supported, SCOPE.supported_intent, SCOPE.action_allowed_in_state]
summary: O que o assistente pode fazer e sob qual política sintética de demonstração ele opera.
---
Este assistente opera com uma política sintética de demonstração, e não com condições reais de um banco. Ele pode ajudar com consultas de saldos, pagamentos e resumos de conta; com a situação dos seus cartões e o bloqueio preventivo de um cartão; com a abertura e o acompanhamento de uma contestação de transação; e com informações sobre produtos de crédito e uma orientação indicativa sobre elegibilidade. Ele só realiza as ações que esta política permite, sempre com a sua confirmação, e informa apenas os resultados que conseguiu verificar.
