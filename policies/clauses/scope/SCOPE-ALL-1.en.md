---
clause_id: SCOPE-ALL-1
version: 1
jurisdiction: ALL
language: en
effective_from: 2026-09-27
synthetic: true
params:
  supported_workflows: [account_inquiry, card_support, dispute, credit]
bound_rules: [SCOPE.workflow_supported, SCOPE.supported_intent, SCOPE.action_allowed_in_state]
summary: What the assistant can do, and the synthetic demonstration policy it operates under.
---
This assistant operates under a synthetic demonstration policy, not under any real bank's terms. It can help with balance, payment, and statement questions; with the status of your cards and a protective card block; with opening and following up a transaction dispute; and with credit product information and an indicative eligibility guide. It only takes the actions this policy allows, always with your confirmation, and it reports only the results it was able to verify.
