---
clause_id: ELG-ALL-2
version: 1
jurisdiction: ALL
language: en
effective_from: 2026-09-27
synthetic: true
params:
  risk_cut_medium_bps: 2000
  risk_cut_high_bps: 3500
  borderline_margin_bps: 100
bound_rules: [ELG.risk_estimate_available, ELG.risk_interval_not_borderline]
summary: Use of the synthetic risk estimate and its uncertainty.
---
The guide considers a risk estimate produced by a model trained on synthetic data, together with its uncertainty range. That estimate is never shown to you and never decides on its own. If it is unavailable, or if its range falls close to the boundary between two risk levels, the result is that a person from the team needs to review your case. These rules are synthetic and make no credit decision.
