---
clause_id: DSP-ALL-1
version: 1
jurisdiction: ALL
language: en
effective_from: 2026-09-27
synthetic: true
params:
  eligible_statuses: [approved]
bound_rules: [DSP.status_eligible]
summary: Which transactions can be disputed, by status.
---
Only completed transactions can be disputed. A pending transaction can still change, so we will ask you to wait until it completes. A declined or reversed transaction did not create a final charge, so there is nothing to dispute.
