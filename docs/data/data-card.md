# Data card

## Provenance

| Data | Origin | Where it lives | In git |
|---|---|---|---|
| Organizer dataset | The Factored AI & Data Hackathon 2026 organizers: "LATAM Bank", fully synthetic, generated for the event (dictionary version 1.0.0, delivery of 2026-08-31) | Organizer S3 bucket (`data/` prefix); local copies under the gitignored `data/` | No |
| Committed sample | 74 organizer customers followed through every table, 2,470 rows plus a 125-row preview, pseudonymized ([`data_platform/sample/README.md`](../../data_platform/sample/README.md), [ADR 0022](../adr/0022-committed-bounded-data-sample.md)) | `data_platform/sample/` | Yes, bounded by CLAUDE.md rule 5 |
| Update-correctness fixture | Team-made, synthetic, labeled in its `FIXTURE.md` | `data_platform/fixtures/late_arrival/` | Yes |
| Test fixtures | Team-made, synthetic, in the test modules (for example the contract dataset) | `services/api/tests/`, `data_platform/tests/` | Yes |
| Portuguese text | None in the organizer data; the evaluation phases generate it and label it team-generated | Later phases | Later phases |

Every organizer row is synthetic: no real customer is represented. The team still treats direct identifiers as personal data (below), because the system must behave as it would with real records.

## Intended use

- **Serving the four workflows** (`account_inquiry`, `card_support`, `dispute`, `credit`) in the prototype: balances with their as-of instant, payment and transfer status, statement summaries, card status and declined purchases, historical complaints, and credit profiles for the synthetic eligibility service.
- **Analysis and ML** in phases 04 and 10: contact-reason demand, complaint funnels and SLAs, intent-router inputs, and credit-risk features.
- **Not for** any real lending decision, real customer contact, or claims about a real bank's customers.

## Credit balance sign convention

`current_balance` is **never negative** on any product (minimum 0.00 over 400,000 products). On credit cards the balance-to-limit ratio averages 0.12 and exceeds 1 on 1.3% of cards. The convention is therefore **`balance_is_amount_owed`**: on a credit product, the balance is the amount owed.

- `bank_agent.adapters.persistence.duckdb.gold.DATASET_CREDIT_BALANCE_CONVENTION` exposes it for balance answers.
- Available credit is computed for **credit cards only**. A loan's `credit_limit` is not a drawable line: mortgage balances exceed it in 49% of rows (personal loans in 2%), so loans show balance and limit without an available-credit figure.
- Transaction amounts are **never negative** either (minimum 5.00; transfers from 100.01, adjustments from 10.00), so the data does not say which way a transfer or an adjustment moved money. They stay `unclassified` in statement totals.

## Personal data handling

| Column | Tables | Treatment |
|---|---|---|
| Document number, names, email, phones, address, birth date | `customers`, `service_agents` | Never served beyond what the identity flow needs: `customers_serving` keeps the first given name, document type and number, and mobile phone (phase 05's mock identity provider); nothing else leaves silver. Pseudonymized in the committed sample |
| `product_number` | `products` | Served only as the last four characters (`product_number_last4`); pseudonymized in the committed sample |
| `ip_address` | `digital_events` | Never read by silver; replaced by documentation addresses in the committed sample |
| Credit score, income, days past due, utilization | `customers`, `products`, `credit_profiles_serving` | Internal columns: never shown to customers or sent to a model (CLAUDE.md section 1) |
| `is_fraud`, `fraud_score`, `response_code` | `transactions` | Internal routing context only |
| Free text (transcripts, complaint descriptions, survey comments) | several | Untrusted text. Profiled: templated, with placeholders such as `{monto}`, no names or identifiers; the complaint description is not served |

No model prompt receives document numbers, full names, emails, phone numbers, or addresses (CLAUDE.md rule 6).

## Known issues found by profiling

| Issue | Evidence | Handling |
|---|---|---|
| The announced ~2% duplicates, late partitions, and schema evolution are absent | 0 exact and 0 primary-key duplicates in every table; one delivery; identical headers | The deduplication, incremental, and evolution logic still runs and reports zero; the fixture proves it |
| Only one snapshot of `customers` and `products` | One root file each | Phase 10 cannot build a forward-looking label from snapshots (BACKLOG) |
| Categorical values in Spanish or outside the dictionary | `Tarjeta Crédito`, `Pasaporte`, `México` and `Mexico`, `Negativo`, contact reasons such as `Transaccional`, branch zone `Urbana`, channel `Web` | Contracts accept both vocabularies; silver maps them to canonical codes |
| `contact_reason` has six coarse values equal to `reason_category` | `Transaccional` 35.0%, `Producto` 22.0%, `Queja` 17.1%, `Técnico` 15.0%, `Comercial` 8.0%, `Retención` 3.0% of 686,296 interactions | Phase 04 maps them to workflows knowing they are coarse |
| Transcripts carry no intent signal | Every transcript opens with one of two balance-inquiry sentences regardless of topic; `detected_intents` is always `consulta_general` | Neither is a valid intent label (phases 04 and 10) |
| `call_transcripts.duration_seconds` is null in 14% of rows although the dictionary says NN | 24,029 rows | Quarantined (`null_in_required_column`), never dropped silently |
| `complaints.affected_product_id` always names another customer's product | 44,570 of 44,570 non-null references | Flagged in silver; served only when it is the customer's own product (never, in this delivery) |
| `digital_events.product_id` names the event customer's own product in 16 of 1.44 million references | 1,094,226 references to another customer's product (the rest are anonymous sessions) | Flagged in silver; digital events are analytics only |
| Nearly every branch reference of customers and agents is an orphan | `customers.registration_branch_id` 149,995 of 150,000; `service_agents.assigned_branch_id` 831 of 833; every other foreign key resolves | Flagged (`is_orphan_*`), listed by `silver.quarantine_orphans`, warning-level relationship tests |
| `amount_usd` is null on every USD transaction and on 5% of COP and ARS ones | 2,437,979 USD rows | Recomputed in silver (rate 1 for USD, as-of rate otherwise), flagged `amount_usd_recomputed` |
| No MXN products or transactions; Mexican customers hold USD products | Product currencies USD, COP, ARS | Served as delivered; income stays in the country currency, so a Mexican customer's income (MXN) and limits (USD) differ in currency, and utilization is computed only within one currency |
| Uniqueness violations | 6 duplicate `product_number`, 13 duplicate `employee_code` | Flagged in silver (`has_duplicate_*`) |
| Timestamps in the future | `last_updated` after the snapshot on 9,316 customers and 25,113 products (up to 2027-06-15) | Flagged in silver (`has_future_last_updated`) |
| Survey scores use narrower ranges than their scales | CSAT 1 to 4, NPS 2 to 7 (no promoters), CES 1 to 4 | Contract ranges by survey type pass; phases that use scores must know |
| `complaints.origin_interaction_id` is always null | 67,095 rows | No complaint-to-interaction link exists |
| Timestamps are UTC, `process_date` is a UTC-6 business date | The 00:00 to 06:00 rollover in every country | Documented in `source-layout.md`; transactions carry a local time |

The generated [quality report](quality-report.md) has the exact counts of the latest build.

## Data-use terms

The data is organizer-provided and subject to the organizer's data-use terms. The terms are not in the repository (the transcribed dictionary carries none), so they **must be checked before the repository is made public; phase 17 re-verifies them**. The committed sample stays within CLAUDE.md rule 5 in the meantime. If the terms forbid redistribution or are unclear, the team stops and asks the human before publishing; history is never rewritten to remove the sample without the human's explicit instruction.
