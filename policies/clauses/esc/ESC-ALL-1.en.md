---
clause_id: ESC-ALL-1
version: 1
jurisdiction: ALL
language: en
effective_from: 2026-09-27
synthetic: true
params:
  repeat_complaint_threshold: 3
  repeat_complaint_lookback_days: 180
  clarification_budget: 2
  tool_retry_budget: 2
bound_rules: [ESC.human_requested, ESC.legal_or_regulator_mention, ESC.clarification_exhausted, ESC.tool_failure_exhausted, ESC.verification_mismatch, ESC.repeat_complainer, ESC.risk_tier_high]
summary: When the conversation moves to a person from the team.
---
A person from the team takes over the conversation when you ask for it; when you mention legal action or a regulator; when you have filed {repeat_complaint_threshold} or more complaints in the last {repeat_complaint_lookback_days} days; when after {clarification_budget} questions we still cannot understand your request; when a system fails after {tool_retry_budget} retries; when the result of an action does not match what was expected; or when we detect risk signals in the session. That person receives a summary of your request, the verified facts, and the actions taken, so you do not have to repeat everything.
