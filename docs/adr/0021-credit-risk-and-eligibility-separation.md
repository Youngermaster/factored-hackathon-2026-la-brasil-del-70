# 0021: Separating conversation handling, risk estimates, and the synthetic eligibility service

- Status: accepted
- Date: 2026-09-26

## Context

The brief's credit rules require separating conversation handling, predictive risk estimates, and eligibility policy; eligibility must come from approved rules or a clearly labeled synthetic policy service; the conversational model must not invent eligibility rules or approve credit; answers show explanations, uncertainty, and review paths; and no live lending decision is authorized. The data has a credit score, an estimated income, and days past due, which are sensitive, and several attributes (gender, birth date, marital status, accent, location, segment) that must never drive a credit estimate.

## Considered options

1. **One credit service** that computes a score and decides eligibility in the same component. Simple, but a model output becomes a decision, and nothing keeps the estimate apart from the customer-facing answer.
2. **Let the language model answer eligibility questions** from the catalog and the profile. Fast to build, but it would invent rules, could imply approval, and would receive sensitive credit facts.
3. **Three components behind separate ports**: the conversation (workflow engine and language model) handles dialogue only; a `RiskEstimator` port returns a probability with an interval and a band; an `EligibilityPolicy` port, implemented by a deterministic synthetic service over `ELG` policy rules, turns the product, the profile, the request, and the estimate into an indicative outcome.

## Decision

Option 3, with the types in `bank_agent/domain/credit.py` and `bank_agent/domain/eligibility.py`, the ports in `bank_agent/ports/models.py` and `bank_agent/ports/eligibility.py`, and the page [credit-separation.md](../architecture/credit-separation.md).

- **The estimate is internal.** `RiskEstimate` fields are marked `Internal()`; so are the credit score, income, days past due, and utilization in `CreditProfile`, the estimate in the execution record, and the risk part of a handoff's credit review. Agents and evaluators see the estimate (handoff, glass box); customers never do, and nothing marked internal is sent to a model. `EligibilityView`, the only customer-facing part, has no field for the estimate or any profile value.
- **No approved outcome exists.** `EligibilityOutcome` is `indicatively_eligible`, `not_eligible`, `review_required`, or `insufficient_data`; application statuses are `submitted`, `under_human_review`, `withdrawn`, and `closed`. A test fails if any card, credit, eligibility, or application enum member or field name contains `approv` or `grant`. A reviewer outside the prototype would make the real decision.
- **Missing data leads to review.** The eligibility port never raises for ordinary input and never returns `indicatively_eligible` with a missing fact; a missing estimate, or one with band `unknown`, gives `review_required`; a mortgage (which needs collateral facts the data lacks) is information only and always `review_required`. The estimator raises `risk_estimator_unavailable` instead of guessing.
- **Protected and proxy attributes are excluded by construction.** `CreditRiskFeatures` is an allowlist without gender, birth date or age, marital status, accent, location below country, segment (the student segment is an age proxy), occupation, or education level, and without identifiers or free text.
- **Everything is labeled synthetic.** Catalog entries, assessments (`eligibility:synthetic@<pack version>`), estimates (`synthetic_data`), and intakes (`synthetic_policy`) carry a literal `True` marker, and every customer answer carries the disclaimer "indicative, not an offer or a decision".
- **Neither component is a tool.** The engine calls both and records them separately in the execution record (`risk_estimates`, `eligibility_assessments`), so no model output can select them and the glass box shows them apart.

## Consequences

- The brief's separation is enforced by types and ports rather than by prompt instructions, and the tests check it.
- A submitted intake is a review item of its own (the phase 13 inbox), not a handoff, so the normal credit path can end resolved; handoffs are reserved for borderline, missing-data, and contested cases.
- Showing the estimate to customers, adding an approval outcome, or adding a protected feature would each need a new decision record and a visible model change.
- The eligibility answer is only as good as the synthetic `ELG` rules (phase 06) and the estimator (phases 09 and 10); both are labeled synthetic and evaluated per workflow.
