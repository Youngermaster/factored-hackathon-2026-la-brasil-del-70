# Workflow scoring pre-registration

Version 1, committed on 2026-09-26 before any score was computed. The machine-readable copy is [`data_platform/analysis/scoring.yaml`](../../data_platform/analysis/scoring.yaml); the mapping is [`data_platform/mappings/workflow_mapping.csv`](../../data_platform/mappings/workflow_mapping.csv). Profiling of the phase 03 warehouse (row counts, value lists, null rates, outcome rates by contact reason) was seen before this document was written and is summarized in [`docs/plans/phase-04.md`](../plans/phase-04.md); no weighted score, rank, or sensitivity result had been computed.

## Purpose and scope

The four workflows are a human decision (CLAUDE.md section 1). The score does not select or drop workflows. It orders the build and depth work across the four and classes each sub-intent as automate, clarify first, or hand off. No score removes a workflow from scope; a workflow that cannot meet the depth bar is cut back to clarify, abstain, or hand off under CLAUDE.md section 1, and that is a separate, documented decision.

## Data

- Source: the full organizer delivery (`BANK_DATA_SOURCE=s3`), silver and gold relations of `data/warehouse/warehouse.duckdb`, delivery `organizer-v1.0.0-2026-08-31`, 2023-06-17 to 2026-06-17.
- Contacts are contact-center interactions (`silver_call_center_interactions`, 686,296) plus complaints (`silver_complaints`, 67,095). Both count as demand.
- An interaction belongs to the workflow its `contact_reason` maps to. A complaint belongs to the workflow its (`category`, `subcategory`) pair maps to; a null subcategory has its own row. `reason_category` rows must agree with the `contact_reason` rows; a disagreement is reported.

## Mapping scenarios

The contact reasons are coarse (six values), so three of the four interaction mappings are assumptions. Every score is computed under three scenarios, all fixed now in the mapping file:

| Scenario | Column | Meaning |
|---|---|---|
| Primary | `workflow_id` | The defensible reading: `Transaccional` to `account_inquiry`, `Producto` to `card_support`, `Queja` to `dispute`, `Comercial` to `credit`, `Técnico` and `Retención` to `other`; complaints about unrecognized charges and undue fees to `dispute`, the rest to `other` |
| Strict | `strict_workflow_id` | Only unambiguous evidence: `Transaccional` to `account_inquiry`; the charge-dispute complaints to `dispute`; everything else to `other` |
| Alternative | `alternative_workflow_id` | As primary, but `Producto` to `credit` |

The primary scenario drives the decision. The strict and alternative scenarios show which conclusions depend on the mapping.

## Criteria, formulas, and columns

Every criterion value lies between 0 and 1. `w` is a workflow; `max` is taken over the four workflows.

| Criterion | Weight | Formula | Columns |
|---|---|---|---|
| Demand | 20 | `D(w) / max D`, where `D(w)` = (interactions of `w` + complaints of `w`) / (all interactions + all complaints) | `call_center_interactions.contact_reason`; `complaints.category`, `subcategory` |
| Pain | 25 | `P(w) / max P`, where `P(w)` is the mean of five components: (a) share not resolved at first contact, (b) share escalated, (c) share of CSAT surveys with a score of 1 or 2, (d) mean handle time of `w` over the largest mean handle time, (e) SLA breach rate of the complaints of `w` (0 when none map to it). A component with no rows is 0 | `was_resolved`, `was_escalated`, `duration_seconds`; `satisfaction_surveys.survey_type`, `main_score`, joined on `interaction_id`; `complaints.sla_breached` |
| Automatable share | 20 | The adjudicated human share (below) when available; otherwise the structured proxy: the share of the workflow's interactions with `was_resolved` true, `was_escalated` false, and `requires_followup` false. 0 when the workflow has no interactions | `was_resolved`, `was_escalated`, `requires_followup`; `data/labeling/automatable_sample.csv` |
| Harm if wrong (inverse) | 10 | `(5 - harm) / 4`, with the harm rubric below | Rubric |
| Data support | 15 | Mean of the measured coverage ratios listed for the workflow (below) | See the item table |
| Demo depth | 10 | Points / 5, one point per behavior in the rubric below | Rubric |

Total score = sum of weight times criterion value, divided by the sum of weights, times 100.

Sentiment is not in the pain composite: `detected_sentiment` is always `neutral` on `Transaccional` contacts, a generator artifact that would bias pain. Complaint outcomes other than the SLA breach are not scored because they are flat across categories in this delivery; they are reported.

### Human labels and the proxy

The automatable share for a workflow comes from human labels only when at least 75 adjudicated items of that workflow's stratum are labeled as matching the workflow (see [`labeling-protocol.md`](labeling-protocol.md)). The share is then (items labeled `yes`) / (matching items labeled `yes`, `no`, or `unclear`), with `unclear` counted as not automatable. Below 75 matching items the proxy is used and every table says "proxy". Machine pre-labels are never used as labels.

### Harm rubric (1 low, 5 high)

| Workflow | Harm | Reason |
|---|---|---|
| `account_inquiry` | 2 | Read only; a wrong or stale figure misleads but moves nothing |
| `card_support` | 3 | A verified protective block is a write; blocking the wrong card disrupts the customer until a human reverses it |
| `dispute` | 3 | Opening a case is a write; a wrong transaction or a missed window affects the customer's money, although a human investigates |
| `credit` | 5 | Regulatory and fair-lending exposure; an indicative result can be read as a decision |

### Demo depth rubric (one point each)

Read path from records; verified write with read-back; clause-backed abstention; human escalation with a structured handoff; a learned component specific to the workflow (the dispute transaction resolver, the credit risk estimator). `account_inquiry` 3, `card_support` 4, `dispute` 5, `credit` 5.

### Data support items

Each item is a ratio measured on the full delivery.

| Item | Definition |
|---|---|
| `product_balance_present` | Non-closed products with a non-null `current_balance` / non-closed products |
| `transactions_classifiable_for_totals` | Transactions whose type is not `transfer` or `adjustment` (their direction is not encoded) / all transactions |
| `payment_transfer_status_present` | Payments and transfers with a non-null `transaction_status` / payments and transfers |
| `transaction_status_present` | Transactions with a non-null `transaction_status` / all transactions |
| `card_expiry_present` | Credit and debit cards with an `expiration_date` / credit and debit cards |
| `card_status_present` | Credit and debit cards with a `product_status` / credit and debit cards |
| `card_blocked_status_observed` | 1 when at least one card has status `blocked`, else 0 |
| `purchase_merchant_present` | Purchases with a `merchant_name` / purchases |
| `complaint_transaction_link_present` | Complaints with a transaction reference / complaints (the dictionary has no such column, so 0) |
| `complaint_own_product_reference` | Complaints whose `affected_product_id` names the complainant's own product / complaints with a reference |
| `complaint_claimed_amount_present` | Dispute-mapped complaints with a `claimed_amount` / dispute-mapped complaints |
| `complaint_status_present` | Dispute-mapped complaints with a `status` / dispute-mapped complaints |
| `customer_credit_score_present` | Customers with a `credit_score` / customers |
| `customer_income_present` | Customers with an `estimated_monthly_income` / customers |
| `credit_product_interest_rate_present` | Credit cards, personal loans, and mortgages with an `interest_rate` / those products |
| `credit_product_days_past_due_present` | The same products with a `days_past_due` / those products |
| `forward_risk_label_available` | 1 when more than one snapshot of `customers` and `products` exists (a label after the features is possible), else 0 |
| `system_owned_record` | 1: the record is created by the system itself (credit application intakes), so no organizer data is needed |

Workflow items: `account_inquiry` the first three; `card_support` expiry, status, blocked observed; `dispute` merchant, transaction link, own product reference, claimed amount; `credit` credit score, income, interest rate, days past due, forward label.

## Sensitivity

1. **Weights.** Each of the six weights moves by plus and minus 5 points (12 variants), and the weights are renormalized to sum to 100. For each variant the ranking is recomputed; the report gives each workflow's score range and rank range, and the number of variants that change the primary order.
2. **Mapping.** The full score under the strict and alternative scenarios.
3. **Cost.** Cost figures at 0.5 and 1.5 times the assumed loaded cost (cost does not enter the score).

## Prioritization rule

- **Build and depth order across the four workflows:** descending total score under the primary scenario and weights. Scores within 2 points are a tie, broken by higher data support, then lower harm. The first workflow built is the reference implementation for the shared engine; every workflow still meets the same depth bar.
- **Weakest candidate for depth:** the lowest-scoring workflow. If a different workflow has the lowest data support or the lowest strict-scenario demand, both are named in the breadth-risk section.
- **Sub-intent classes inside a workflow.** Capability comes from CLAUDE.md section 1: 1 for a self-service read or a verified write, 0.5 for an intake or an indicative result recorded for human review, 0 for escalation only by design.
  - **Hand off:** capability 0.
  - **Clarify first:** capability above 0 and sub-intent data support below 0.5; the system answers only what the records support and otherwise asks, abstains with a clause, or hands off.
  - **Automate:** capability above 0 and data support of at least 0.5. Within a workflow, automated sub-intents are ordered by sub-intent score.
- **Sub-intent score:** the same weights. Demand, pain, and demo depth are inherited from the workflow (the data cannot split coarse reasons into sub-intents); automatable share is the workflow value times the capability; harm and data support use the sub-intent's own rubric value and items (`scoring.yaml`).

## Statistics

Bootstrap 95% intervals (1,000 resamples, seed 20260926) for rates and means. For a rate, a resample of n Bernoulli outcomes is drawn as a binomial count, which is the same distribution. Segment cells with fewer than 100 interactions or 30 surveys are flagged as small.

## Stop conditions checked by the analysis

- A workflow without data support for its core read path: no payment or transfer transactions (`account_inquiry`), no card products (`card_support`), no purchases (`dispute`), no credit products with a credit limit or an interest rate (`credit`).
- More than 5% of interaction or complaint volume without a mapping row (a row mapping to `other` counts as mapped).
- `credit_score`, `estimated_monthly_income`, or `days_past_due` (on credit products) missing for most customers or products.

## Changes

| Version | Date | Change | Reason |
|---|---|---|---|
| 1 | 2026-09-26 | Initial pre-registration with the prompt's default weights | Committed before results. The human may adjust the weights later as a new version; results under both versions are kept |
