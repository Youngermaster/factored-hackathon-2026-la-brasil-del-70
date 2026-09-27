# Labeling protocol: router validation sample

Status: the sheet is exported and **no item is labeled yet** (a pending human action in [`docs/PROGRESS.md`](../PROGRESS.md)). Until labels exist, [`router.md`](router.md) reports agreement and label accuracy as pending.

## What is labeled and why

Every router utterance is team-authored or derived from a team-authored seed ([model card](../models/router.md)). The labels were assigned by the authors, so two things need an independent check:

- Is the assigned intent right?
- Does the text read like something a customer in that locale would write?

The sample checks both on the held-out test split, which is what the reported metrics are measured on.

| Aspect | Rule |
|---|---|
| File | `ml/corpus/router/validation/router_validation_v1.csv` (team-written text, committed) |
| Key | `ml/corpus/router/validation/router_validation_v1.key.csv` holds the assigned intent and provenance. **Labelers do not open it** |
| Population | Test-split items of the router dataset `router-v1` |
| Stratum | Intent by locale (17 x 4 = 68 cells) |
| Allocation | 3 items per cell by the salted order `sha256("router-validation-v1:" + item_id)`, trimmed to 200 by removing at most one item from a cell (every cell keeps at least two) |
| Regeneration | `bank-ml router export-validation`; a sheet that holds any label is never overwritten (`kept`) |

## Columns to fill

| Column | Values |
|---|---|
| `labeler_1_intent`, `labeler_2_intent` | One `Intent` value: `dispute_new`, `dispute_status`, `card_block`, `card_status`, `card_unblock_request`, `card_replacement_request`, `balance_inquiry`, `payment_status`, `statement_request`, `credit_product_info`, `credit_eligibility`, `credit_application`, `credit_application_status`, `informational`, `human_request`, `greeting_or_other`, `unsupported` |
| `labeler_1_natural`, `labeler_2_natural` | `yes` (a customer in that locale could write this), `no`, or `unclear` |
| `adjudicated_intent` | The agreed intent after adjudication |
| `notes` | The reason for any adjudication, or a note on unnatural wording |

The label definitions are the ones in the paraphrase prompt descriptions (`bank_ml/router/paraphrase.py`, `DESCRIPTIONS`) and in the seed-authoring brief summarized in the model card. `unsupported` covers both unsupported banking requests (a transfer, an investment, a limit increase) and off-domain text.

## Procedure

1. Two labelers, one native Spanish and one native Brazilian Portuguese reader for the pt-BR rows (or two per language when available), label independently without the key and without each other's answers.
2. Disagreements on the intent are adjudicated by a third person or by the two together. Agreed items copy the agreed value into `adjudicated_intent`.
3. Run `bank-ml router evaluate` (or `make train`). The report then shows Cohen's kappa between labelers and the label accuracy (adjudicated intent against the assigned intent).
4. A kappa below 0.6, or a label accuracy below 90%, means the definitions or the seeds need revision before the router numbers are trusted. Fix the seeds, retrain, and re-export a new version (`router_validation_v2`).
5. Items marked `natural = no` are rewritten in the seed files (a new corpus version) even when their label is right.

## Known limitation

The sample validates labels and naturalness of the evaluation text. It cannot show how real customers phrase requests; only production text, under the organizer's terms and the privacy rules, could do that.
