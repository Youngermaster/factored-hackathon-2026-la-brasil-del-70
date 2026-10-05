---
clause_id: DSP-AR-3
version: 2
jurisdiction: AR
language: en
effective_from: 2026-09-27
synthetic: true
params:
  auto_intake_max_amount: {amount: "600000.00", currency: ARS}
  usd_exchange_rate: {amount: "350.75", currency: ARS}
  usd_exchange_rate_as_of: "2025-11-03"
  usd_exchange_rate_source: "synthetic rate derived from the organizer daily_exchange_rates sample (ARS to USD 0.002851)"
bound_rules: [DSP.amount_within_auto_limit]
summary: Synthetic maximum amount for automatic dispute intake in Argentina.
---
The assistant can record disputes for amounts up to {auto_intake_max_amount}. For a larger amount, a person from the team takes your case from the start to review it with you.
