---
clause_id: DSP-ALL-2
version: 1
jurisdiction: ALL
language: en
effective_from: 2026-09-27
synthetic: true
params:
  required_fields: [transaction, reason, disputed_amount]
bound_rules: [DSP.required_fields_present]
summary: Information needed to record a dispute.
---
To record a dispute we need to identify the transaction with you, the reason, and the amount you dispute, which cannot exceed the transaction amount. If several transactions look alike, we will show you the options so you can choose the right one; we never choose for you.
