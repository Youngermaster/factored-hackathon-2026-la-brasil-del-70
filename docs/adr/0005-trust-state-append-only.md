# 0005: Trust state as append-only evidence with a monotonic risk tier

- Status: accepted
- Date: 2026-09-26

## Context

Several signals should make the assistant more careful for the rest of a session: failed one-time codes, a request for another customer's transaction, prompt-injection text, a caller admitting they are not the account holder, an unusual amount. The policy kernel (phase 06) uses the resulting risk to require step-up or to escalate (`ESC.risk_tier_high`). If risk could go down within a session, an attacker could probe, wait, or log in again until the system relaxed. Risk evidence must also be auditable without storing attack payloads.

## Considered options

1. **A mutable risk score** on the session, raised and lowered by the workflow. Simple, but any code path can relax it, and the history of why it changed is lost.
2. **Append-only events with a derived tier that is monotone in the events**, stored per session.
3. **Option 2 keyed by a session lineage**, which survives session rotation (step-up) and re-authentication that resumes the same conversation.

## Decision

Option 3, implemented in `bank_agent/domain/trust.py`:

- `TrustEvent` holds a kind, a time, the turn, the detector (for example `injection:heuristic@1`), an optional evidence reference, and a machine-readable detail code. It has no free-text field, so an injection payload is never copied into risk evidence.
- `TrustState` is an immutable tuple of events. `append` returns a new state and raises `TrustStateViolationError` for an event older than the last one; assignment raises because the model is frozen.
- Each kind has a fixed severity: `failed_otp` and `unusual_amount` are low; `otp_lockout`, `injection_detected`, and `third_party_admission` are medium; `cross_customer_probe` and `identity_mismatch` are high.
- `risk_tier` is the highest tier reached by these rules: one medium event gives `elevated`, one high event gives `high`, two medium-or-higher events give `high`, and three low events give `elevated`. Each rule depends only on counts that can grow, so appending can never lower the tier. A Hypothesis test checks this over arbitrary event sequences.
- The severities and thresholds live in the domain for now (approved with the phase 02 plan). Phase 06 may move the thresholds into the policy pack if the team wants them reviewed as policy data.
- The state is keyed by `LineageId`. A session keeps its lineage when it rotates, and a re-authenticated session that resumes a conversation joins the conversation's lineage, so logging in again does not reset risk.
- The `SessionStore` port stores trust events outside the turn's unit of work, on purpose: if a turn fails after an event was detected, the evidence persists. This fails closed.

## Consequences

- No code path can relax risk within a lineage; the only way to lower it is a new, unrelated lineage (a new conversation after a fresh login), which is an explicit product decision rather than an accident.
- Tuning the tier rules is a reviewed domain change with tests, not a configuration tweak.
- Trust events are not rolled back with a failed turn, so a retried turn may add a second event of the same kind; the tier rules count events, so a retry can raise the tier sooner. This errs on the side of caution.
