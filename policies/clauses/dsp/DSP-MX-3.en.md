---
clause_id: DSP-MX-3
version: 1
jurisdiction: MX
language: en
effective_from: 2026-09-27
synthetic: true
params:
  auto_intake_max_amount: {amount: "10000.00", currency: MXN}
bound_rules: [DSP.amount_within_auto_limit]
summary: Synthetic maximum amount for automatic dispute intake in Mexico.
---
The assistant can record disputes for amounts up to {auto_intake_max_amount}. For a larger amount, a person from the team takes your case from the start to review it with you.
