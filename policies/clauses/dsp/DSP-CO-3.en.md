---
clause_id: DSP-CO-3
version: 2
jurisdiction: CO
language: en
effective_from: 2026-09-27
synthetic: true
params:
  auto_intake_max_amount: {amount: "2000000.00", currency: COP}
  usd_exchange_rate: {amount: "4000.00", currency: COP}
  usd_exchange_rate_as_of: "2026-06-11"
  usd_exchange_rate_source: "synthetic rate derived from the organizer daily_exchange_rates sample (COP to USD 0.00025)"
bound_rules: [DSP.amount_within_auto_limit]
summary: Synthetic maximum amount for automatic dispute intake in Colombia.
---
The assistant can record disputes for amounts up to {auto_intake_max_amount}. For a larger amount, a person from the team takes your case from the start to review it with you.
