---
clause_id: ACC-ALL-2
version: 1
jurisdiction: ALL
language: pt
effective_from: 2026-09-27
synthetic: true
params:
  max_statement_days: 92
bound_rules: [ACC.statement_period_within_limit]
summary: Período máximo de um resumo de movimentações.
---
Podemos preparar um resumo de movimentações de um produto para um período de até {max_statement_days} dias. O resumo mostra os totais por moeda das operações efetivadas e indica à parte as operações pendentes, recusadas ou estornadas e as que não podem ser classificadas como débito ou crédito.
