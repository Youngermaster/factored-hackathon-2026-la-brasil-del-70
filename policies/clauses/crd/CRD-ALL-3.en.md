---
clause_id: CRD-ALL-3
version: 1
jurisdiction: ALL
language: en
effective_from: 2026-09-27
synthetic: true
params:
  handoff_sla_hours: 24
bound_rules: [CRD.unblock_requires_human, CRD.replacement_requires_human]
summary: Card unblocking and replacement are handled by a person.
---
Unblocking a card and issuing a replacement card require identity and fraud checks the assistant cannot perform. We therefore pass your request to a person from the team, with the details of what you asked for and of the card, who will contact you within {handoff_sla_hours} hours. In the meantime the card keeps its current status.
