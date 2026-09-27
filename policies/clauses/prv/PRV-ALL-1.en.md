---
clause_id: PRV-ALL-1
version: 1
jurisdiction: ALL
language: en
effective_from: 2026-09-27
synthetic: true
params:
  masked_digits: 4
bound_rules: [PRV.no_cross_customer_access]
summary: What information is shown, to whom, and how numbers are masked.
---
We only show information about the products of the person verified in the session. Card and account numbers are masked, showing their last {masked_digits} digits. We neither confirm nor deny the existence of products, transactions, or people that do not belong to you.
