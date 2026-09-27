---
clause_id: DSP-ALL-2
version: 1
jurisdiction: ALL
language: pt
effective_from: 2026-09-27
synthetic: true
params:
  required_fields: [transaction, reason, disputed_amount]
bound_rules: [DSP.required_fields_present]
summary: Informações necessárias para registrar uma contestação.
---
Para registrar uma contestação, precisamos identificar a transação com você, o motivo e o valor contestado, que não pode ser maior que o valor da transação. Se houver várias transações parecidas, mostraremos as opções para você escolher a correta; nunca escolhemos por você.
