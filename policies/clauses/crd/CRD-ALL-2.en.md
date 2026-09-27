---
clause_id: CRD-ALL-2
version: 1
jurisdiction: ALL
language: en
effective_from: 2026-09-27
synthetic: true
params:
  block_requires_step_up: true
  step_up_window_minutes: 5
bound_rules: [CRD.card_active, CRD.block_requires_step_up]
summary: Protective card block, stronger verification, and consequences.
---
You can put a protective block on an active card if it was lost or stolen, or if you see activity you do not recognize. Before blocking it we will ask for a stronger verification, valid for {step_up_window_minutes} minutes, and your explicit confirmation.

The block takes effect immediately: the card stops working for purchases, withdrawals, and recurring charges, and linked automatic payments may fail. The assistant cannot unblock the card or issue a new one; a person from the team handles those requests. We will confirm the block only after checking in the records that the card is blocked.
