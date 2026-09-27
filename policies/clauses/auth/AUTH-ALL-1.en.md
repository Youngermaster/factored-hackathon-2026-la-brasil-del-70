---
clause_id: AUTH-ALL-1
version: 1
jurisdiction: ALL
language: en
effective_from: 2026-09-27
synthetic: true
params:
  step_up_window_minutes: 5
  session_idle_minutes: 15
  elevated_risk_required_level: step_up
bound_rules: [AUTH.session_valid, AUTH.required_level, AUTH.step_up_valid]
summary: Identity verification required to read data and for every action.
---
To see information about your products you need a session verified with a one-time code sent to your registered phone. For any action, such as blocking a card, opening a dispute, or recording a credit application, we will also ask for a stronger verification with a new code, valid for {step_up_window_minutes} minutes. The session ends after {session_idle_minutes} minutes without activity.

If we detect risk signals in the conversation, we may also ask for the stronger verification before showing you any information.
