---
clause_id: CRD-ALL-3
version: 1
jurisdiction: ALL
language: pt
effective_from: 2026-09-27
synthetic: true
params:
  handoff_sla_hours: 24
bound_rules: [CRD.unblock_requires_human, CRD.replacement_requires_human]
summary: O desbloqueio e a reposição de um cartão são atendidos por uma pessoa.
---
O desbloqueio de um cartão e a emissão de um cartão de reposição exigem verificações de identidade e de fraude que o assistente não pode realizar. Por isso, encaminhamos a sua solicitação a uma pessoa da equipe, com o detalhe do pedido e do cartão, para que entre em contato em até {handoff_sla_hours} horas. Enquanto isso, o cartão continua na situação atual.
