# Labeling protocol: automatable share

Status: the sample is exported and machine pre-labels exist; **the human labeling has not started** (pending human action in [`docs/PROGRESS.md`](../PROGRESS.md)). Until humans label, every score uses the pre-registered structured proxy, and every report says so.

## What is labeled

`make analysis DATA_SOURCE=s3` writes `data/labeling/automatable_sample.csv` (gitignored, never committed): 150 transcripts per in-scope workflow, 600 in total.

| Aspect | Rule |
|---|---|
| Population | Contact-center interactions with a served transcript and non-empty `customer_text` (147,292 in the full delivery) |
| Stratum | The workflow the interaction's `contact_reason` maps to under the primary mapping ([`workflow_mapping.csv`](../../data_platform/mappings/workflow_mapping.csv)); `other` is not sampled |
| Allocation | Equal across the three countries (50 each); a country short of rows passes its shortfall to the others |
| Order | Ascending `sha256("labeling-v1:" + interaction_id)`, so the sample is reproducible and not hand-picked |
| Columns shown | `item_id`, `interaction_id` (a synthetic organizer id), `workflow_stratum`, `customer_text`, and empty label columns. No other field, no name, no document number |
| Floor | 75 items per workflow is the documented floor if the team cannot label 150; the intervals then widen (a share near 50% has a 95% interval of about plus or minus 11 points at 75 items and 8 points at 150) |

Machine pre-labels are written to a **separate file**, `data/labeling/automatable_prelabels.csv`, with `review_status=pending`. Labelers must not open it before labeling, so they do not anchor on it. The analysis never reads pre-labels as labels.

A rerun of `make analysis` never overwrites `automatable_sample.csv` once any label column holds a value; it prints `labeling file: kept`.

## The two questions per item

Each labeler answers two questions about the customer text as written, each with `yes`, `no`, or `unclear`:

1. **`matches_workflow`**: does the text ask for something inside the item's workflow stratum?
2. **`resolvable`**: can the system resolve what the text asks **from the customer's records plus policy, without a human**, under the scope in CLAUDE.md section 1?

What "resolvable" means per workflow:

| Workflow | `yes` | `no` |
|---|---|---|
| `account_inquiry` | A balance, payment or transfer status, or statement summary, answered from the records with the as-of date | Documents, statement delivery, anything not in the records, or anything about another customer |
| `card_support` | Card status, or a protective block completed with confirmation, step-up, and a verified read-back | Unblocking or replacing a card (these always go to a human) |
| `dispute` | Opening a dispute case with a verified read-back (intake), or answering the status of an existing case. The investigation outcome is not required | A refund decision, a legal complaint, or a case that needs a human by policy (amount above the limit, repeat complainer) |
| `credit` | An answer from the synthetic product catalog, an indicative result from the synthetic eligibility rules with reasons and a review path, or an application intake recorded for human review | **A lending decision is never automatable.** Anything that asks for approval, a limit, or a rate decision is `no` |

`unclear` is for text that cannot be judged (fragments, several requests at once). It counts as not automatable.

## Procedure

1. Two labelers label every item independently (`labeler_1_*`, `labeler_2_*`), without seeing each other's answers or the pre-labels.
2. Items where they disagree on either question are adjudicated by a third person, or by the two labelers together, and the result goes to `adjudicated_resolvable` and `adjudicated_matches_workflow`. Items where they agree copy the agreed value. `notes` records the reason for any adjudication.
3. The analysis reports Cohen's kappa for `resolvable` on double-labeled items. A kappa below 0.6 means the definitions above need revision before the labels are used.
4. When only one labeler is available, fill labeler 1 and the adjudicated columns, and say so in `notes`; the report then shows no kappa.

## How the labels are used

- For each workflow, the labeled automatable share is (items with `adjudicated_resolvable = yes`) / (items with `adjudicated_matches_workflow = yes`). Only items whose text matches the workflow count.
- The share replaces the proxy for a workflow only when at least 75 adjudicated items match it (pre-registered). Below that the report says `insufficient matching labels (n of 75)` and the proxy stays.
- The label-based addressable cost uses the same share; until then the report says `pending human labels`.

## Known limitation: transcripts cannot measure three of the four workflows

Profiling in phases 03 and 04 found that transcripts carry no workflow signal: 42 distinct customer texts, all built from two balance questions ("the balance of my credit card", "my savings account balance") plus closing phrases, whatever the contact reason (Cramer's V between contact reason and the balance question: 0.008). `detected_intents` is always `consulta_general`, and `main_topics` is a copy of `contact_reason`.

Consequences, stated before anyone labels:

- Items in the `account_inquiry` stratum will mostly match and be resolvable (a balance question), which is expected and measures a balance question, not the whole workflow.
- Items in the `card_support`, `dispute`, and `credit` strata will almost all be labeled `matches_workflow = no`. The labels will then confirm, with a measured count, that transcripts cannot give an automatable share for those workflows, and their scores keep the proxy.
- **For phase 10 (router training and evaluation):** the organizer transcripts cannot serve as intent-labeled utterances. Router training and evaluation text for all four workflows must be team-authored or paraphrased by a language model from team-authored seeds, labeled as such (`provenance: team_authored` or `llm_paraphrased`), in Spanish and Portuguese, with the split rules phase 10 defines. Evaluation text must never be generated by the same prompt that generated training text.

## Machine pre-label rule

`bank_data.analysis.labeling.prelabel`: the first matching keyword rule decides a topic (`saldo` for a balance question, card loss or block words, dispute words, credit words). A balance question is pre-labeled `resolvable = yes` and `matches_workflow = yes` only in the `account_inquiry` stratum; other topics are `unclear`. On the full delivery every one of the 600 items is a balance question, so the pre-labels read `matches_workflow = no` for all 450 items outside `account_inquiry`. They are a sanity check for the labelers' results, not labels.
