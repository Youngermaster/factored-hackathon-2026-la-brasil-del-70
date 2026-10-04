# Demo personas

`make seed` (or `bank-data seed --customers N`) loads the demo personas and a deterministic customer subset from the gold serving tables into PostgreSQL. This page records how personas are chosen and what each one demonstrates. It records selection criteria only: no names, document numbers, phones, or balances. The seed prints which internal customer id each persona resolved to.

## How personas are chosen

- The persona file is `data_platform/seed/personas.yaml`; each persona names a criterion implemented in `data_platform/src/bank_data/seed/criteria.py` as a SQL predicate over the gold serving views.
- Candidates are active customers with a phone on file (document identification needs its last four digits), ordered by `md5(seed || customer_id)` with the seed `bank-demo-personas-v1`. Each persona takes the first candidate that no earlier persona took, so the choice is deterministic for a given delivery and never hand-picked.
- Coverage is added after the personas: at least two customers per country and at least one per segment (premium, plus, basic, student), then a seeded-hash fill up to `--customers` (default 200).
- "Recent" means within 30 days before the dataset snapshot (2026-06-17). Demo conversations therefore talk about June 2026 data; policy windows (for example the dispute window) are evaluated against the data's as-of date (`POLICY_DATA_AS_OF`, default 2026-06-17), not the wall clock.
- The organizer data has no dispute cases and no credit applications, so the seed synthesizes exactly two records, labeled `seed` in their ids and idempotency keys: one open dispute case on the latest approved card purchase of `dsp-mx-open-case`, and one submitted application intake for `cre-co-application` (product code `CO-PL-STANDARD`, published in the synthetic catalog under `policies/credit/`).
- The seeded case opens at the seeding instant, exactly as the service opens a case (on the wall clock, while dispute windows are evaluated against the data's as-of date), and its SLA is the Mexican dispute resolution target of the policy pack (`DSP-MX-2`, 45 days) from then. Its status question therefore answers with the case and its deadline for 45 days after the seed. Before phase 17 the case opened the day after the purchase, so on a demo seeded months after the data snapshot it read as overdue and escalated. Re-running the seed never moves an existing case (seeded records are inserted only when missing), so a demo is recorded on a fresh volume.

## The committed sample supports 12 of the 16 customer personas

`make seed` on the committed sample (the default source, and the gold the deployed demo's job image carries) reads `data_platform/seed/personas.sample.yaml`: 12 customer personas and the two staff personas. The sample has no customer that matches `acc-co-payments`, `acc-ar-similar-transfers`, `dsp-ar-repeat-complainer`, or `dsp-mx-similar-purchases` (checked in phase 17 against the sample's gold), so those four exist only after a seed from the full delivery (`make pipeline DATA_SOURCE=s3`, then `make seed DATA_SOURCE=s3`). The sign-in page lists them in a separate group that says so, and the demo guide uses only the 12 (a `data_platform` unit test checks it).
- A persona that matches nobody stops the seed with an error naming it; nothing is loaded.

## Customer personas

| Persona | Country | Criterion | Demonstrates |
|---|---|---|---|
| `acc-mx-accounts` | MX | An active checking and an active savings account, both with balances | Balances with their as-of instant |
| `acc-co-payments` | CO | A pending payment and a reversed payment | Payment status |
| `acc-ar-similar-transfers` | AR | Two transfers within 7 days whose amounts differ by at most 5% | Payment ambiguity: the assistant asks which one |
| `crd-mx-two-cards` | MX | Two or more active cards | Card ambiguity, then a protective block with step-up |
| `crd-co-declined` | CO | A declined card purchase | Card status and a declined purchase (the response code is not interpreted) |
| `crd-ar-expired` | AR | A card past its expiry date | Status answer; the replacement request is handed off |
| `crd-mx-blocked` | MX | An already blocked card | The unblock request is handed off (no unblock tool exists) |
| `dsp-co-unrecognized` | CO | A recent approved purchase with a merchant on an active card | Unrecognized-charge dispute intake with an optional protective block |
| `dsp-mx-open-case` | MX | A recent approved card purchase, plus the seeded open case | Dispute status with the SLA |
| `dsp-ar-repeat-complainer` | AR | Three or more complaints in the year before the snapshot | Repeat-complainer escalation |
| `dsp-mx-similar-purchases` | MX | Three or more purchases at one merchant within 30 days | Ambiguous transaction: the assistant offers at most three options |
| `cre-mx-complete` | MX | Credit score 700 or more, income, tenure, and utilization on file, no days past due | Indicative eligibility with reasons, uncertainty, and a review path |
| `cre-co-no-income` | CO | A credit score but no income on file | Insufficient data: the assistant asks for the missing fact |
| `cre-ar-borderline` | AR | Credit score from 640 to 660 with income and no days past due | Borderline result sent to human review |
| `cre-mx-past-due` | MX | Days past due on a credit product | Review required |
| `cre-co-application` | CO | A complete credit profile, plus the seeded application intake | Application status |

## Staff personas

| Persona | Role | Use |
|---|---|---|
| `agent-demo-01` | agent | The agent console: handoff inbox, claiming and resolving handoffs, reading referenced cases and applications |
| `evaluator-demo-01` | evaluator | Execution records and audit events; evaluation runs use the separate `eval` schema |

## Paths each workflow can play

Every path is played in Spanish and in Portuguese by the same persona: the organizer data holds customers in Mexico, Colombia, and Argentina only, so the conversation language is the customer's choice, not a property of the data. Escalation triggers that come from the conversation itself (asking for a human, distress, a legal mention) work with any persona.

Personas marked "full delivery" exist only after a seed from the full delivery (previous section).

| Workflow | Normal | Ambiguous or unsupported | Human escalation |
|---|---|---|---|
| `account_inquiry` | `acc-mx-accounts` (balances), `acc-co-payments` (payment status, full delivery) | `acc-mx-accounts` asking about "my transfer" without details (it asks for them), `acc-ar-similar-transfers` (which transfer, full delivery), a transfer or a statement document (clause-backed abstention) | Any persona asking for a human or contesting a balance, for example `acc-mx-accounts` |
| `card_support` | `crd-mx-two-cards` (status, then a protective block) and `crd-co-declined` | `crd-mx-two-cards` and `crd-co-declined` (which card) | `crd-mx-blocked` (unblock request) and `crd-ar-expired` (replacement request) |
| `dispute` | `dsp-co-unrecognized` (intake from the statement), `dsp-mx-open-case` (status with the deadline) | `dsp-co-unrecognized` without details (it asks for the date, amount, and merchant), `dsp-mx-similar-purchases` (which transaction, full delivery) | A complaint to the regulator with any persona; a charge above the automatic limit or in another currency than the limit (`DSP-<country>-3`: 10,000 MXN, 2,000,000 COP, 600,000 ARS); `dsp-ar-repeat-complainer` (full delivery) |
| `credit` | `cre-mx-complete` (catalog and an indicative result), `cre-co-application` (status) | `cre-co-no-income` (missing income); a mortgage question (information only); a demand for approval (abstention) | `cre-ar-borderline` and `cre-mx-past-due` (review or missing information, then the review button); a contested result |

On the committed sample the synthetic eligibility service answers `cre-mx-complete` with "review required" (tenure below the minimum, and the risk estimate near a band boundary) and `cre-ar-borderline` with "insufficient data" (no delinquency information); both show reasons, uncertainty, and the review path. The full delivery selects other customers for the same criteria, so the outcomes can differ there.

Cross-customer attempts are played by any persona asking about another customer's product, transaction, case, or application id: every tool treats it exactly like an unknown id, and the database would return nothing even if a tool did not (`docs/security/data-isolation.md`).

## Logging in as a persona

1. Start a login with the persona id (for example `crd-mx-two-cards`), or with the customer's document number plus the last four digits of the phone on file.
2. With `DEMO_MODE=true` the one-time code is returned with the challenge so the UI can show it, labeled as a demo. Without demo mode the code is never shown or logged.
3. Enter the code to receive a session. Writes such as a card block ask for a fresh code first (step-up).

The flows are described in `docs/security/identity-and-sessions.md`, and the HTTP routes in `docs/api/README.md`.

## Reproducing the seed

```bash
make up                         # the compose PostgreSQL (reads .env)
make pipeline                   # gold from the committed sample (or DATA_SOURCE=s3 for the full delivery)
make seed                       # migrate, then load; running it again changes nothing
make seed SEED_CUSTOMERS=500    # a larger subset; the personas are always included
```

The seed reads `POSTGRES_ADMIN_PASSWORD` and `SESSION_SECRET` through the service settings and never prints them. Changing `SESSION_SECRET` changes every identity lookup digest, so seed again after rotating it.
