---
clause_id: CRD-ALL-2
version: 1
jurisdiction: ALL
language: pt
effective_from: 2026-09-27
synthetic: true
params:
  block_requires_step_up: true
  step_up_window_minutes: 5
bound_rules: [CRD.card_active, CRD.block_requires_step_up]
summary: Bloqueio preventivo de um cartão, verificação reforçada e consequências.
---
Você pode bloquear de forma preventiva um cartão ativo se o perdeu, se ele foi roubado ou se vê movimentações que não reconhece. Antes do bloqueio, pediremos uma verificação reforçada, válida por {step_up_window_minutes} minutos, e a sua confirmação expressa.

O bloqueio é imediato: o cartão deixa de funcionar para compras, saques e cobranças recorrentes, e os pagamentos automáticos associados podem falhar. O assistente não pode desbloquear o cartão nem emitir um novo; esses pedidos são atendidos por uma pessoa da equipe. Só confirmaremos o bloqueio depois de verificar nos registros que o cartão ficou bloqueado.
