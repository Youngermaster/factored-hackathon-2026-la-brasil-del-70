# Retrieval relevance judgments: format and labeling protocol

The judgments in `evals/data/retrieval_judgments.v1.jsonl` measure open retrieval for informational questions ([grounding](../workflows/grounding.md)). They were drafted by the team from the policy catalog ([catalog](../policy/catalog.md)) in phase 07 and are **pending human review**: every line has `review_status: pending`, and the results in [retrieval.md](retrieval.md) are provisional until the review below is done.

## Format

One JSON object per line.

| Field | Meaning |
|---|---|
| `query_id` | `acc-NN`, `crd-NN`, `dsp-NN`, `cre-NN`, or `oos-NN`; never reused |
| `workflow` | `account_inquiry`, `card_support`, `dispute`, `credit`, or `out_of_scope` |
| `query` | What a customer might type, in the locale's register (voseo for es-AR) |
| `language`, `locale` | `es` with `es-MX`, `es-CO`, or `es-AR`; `pt` with `pt-BR` |
| `jurisdiction` | `MX`, `CO`, or `AR`: the verified customer's country, which filters the corpus |
| `relevant` | Graded clauses: `{"clause_id": "DSP-MX-1", "grade": 2}`; empty for out-of-scope queries |
| `expected` | `answer` when at least one clause is relevant, `abstain` for out-of-scope queries |
| `split` | `dev` (tunes thresholds) or `test` (reported); fixed per query, never moved after results are seen |
| `provenance` | `team_generated` (no organizer data, no model paraphrase) |
| `review_status` | `pending`, `reviewed`, or `rejected` |
| `notes` | Optional reviewer note |

## Starter set (version 1)

| Workflow | Queries | es-MX | es-CO | es-AR | pt-BR | Dev | Test |
|---|---|---|---|---|---|---|---|
| `account_inquiry` | 20 | 5 | 5 | 5 | 5 | 8 | 12 |
| `card_support` | 20 | 5 | 5 | 5 | 5 | 8 | 12 |
| `dispute` | 20 | 5 | 5 | 5 | 5 | 8 | 12 |
| `credit` | 20 | 5 | 5 | 5 | 5 | 8 | 12 |
| `out_of_scope` | 20 | 5 | 5 | 5 | 5 | 8 | 12 |

Portuguese queries rotate their jurisdiction across MX, CO, and AR (the bank serves Portuguese speakers in all three). Within each locale block of five, two queries are dev and three are test, so both splits cover every workflow and locale.

## Labeling rules

1. **Grades.** 2 for the clause that governs the question (the one the answer must cite); 1 for a clause that adds a useful condition or a next step; 3 is reserved for a clause that fully answers a narrow factual question on its own and is not used in version 1. Label every clause a careful agent would cite, not only the best one.
2. **Jurisdiction.** A country-specific question takes the clause of the query's jurisdiction (`DSP-CO-1` for a Colombian customer). Never label a clause the customer cannot see; `bank-eval retrieval` refuses such a line.
3. **Eligibility.** ELG clauses are never relevant: open retrieval never supplies an eligibility rule. Credit questions label CRE, ESC-ALL-4, or INF-ALL-3 clauses; a question that can only be answered by the eligibility service belongs to the credit workflow, not to this set.
4. **Out of scope.** Queries no clause answers (weather, sports, recipes, branch hours, exchange rates) expect abstention. Hard negatives that share words with the pack ("¿Dónde queda el cajero más cercano?") are welcome. A question the pack declines with a clause (`SCOPE-ALL-2`, `ACC-ALL-3`, `CRE-ALL-3`) is in scope: the declining clause is relevant.
5. **Leakage.** Write the query before looking at any retriever output; do not copy clause sentences into queries; do not tune on `test`. The split is part of the line and stays fixed.
6. **No personal data.** Queries never contain names, document numbers, card numbers, or amounts from records.

## Review protocol (pending)

1. Two reviewers per language (one Spanish, one Portuguese speaker) read every line in their language independently, with the clause texts at hand.
2. For each line they confirm or change the query wording (natural for the locale), the relevant clauses, the grades, and the expected behavior, and set `review_status` to `reviewed` or `rejected` with a `notes` entry for any change or rejection.
3. Disagreements on relevance or grade are adjudicated by a third person; record the adjudicated label and keep the note.
4. A reviewed file becomes `retrieval_judgments.v2.jsonl` (version 1 stays unchanged for reproducibility); rerun `make eval-retrieval` and record the reviewers, the date, and the agreement (share of lines unchanged) in `docs/PROGRESS.md`.

## Extending the set

Add lines to a new version file, 20 or more per workflow, keeping the locale balance and assigning `dev` or `test` before any run (for example, alternate by query id). Extend the test split first: per-workflow cells of 12 in-scope queries move by about 0.08 per query.
