# 0012: Bound policies for workflow states, with open retrieval only for informational questions

- Status: accepted
- Date: 2026-09-27

## Context

The brief asks that every response is grounded in verified records, that explanations come from sources and policy rules, and that relevance judgments are valid and free of leakage. The four workflows (CLAUDE.md section 1) each move through a state machine whose rules and customer-facing clauses are fixed by `policies/bindings.yaml`. Customers also ask general questions ("how many days do I have to dispute a charge?") that no single state answers. Credit adds a hard constraint: retrieved text must never supply an eligibility rule, because eligibility comes only from the synthetic eligibility service.

## Considered options

1. **Open retrieval everywhere.** Every turn retrieves the most similar clauses. Simple, but the clause governing a decision would depend on phrasing and on a similarity score; a state could cite a clause of another country or miss the one its rule used, and explanations would stop matching decisions.
2. **Bound clauses only.** Deterministic, but informational questions outside a state get no grounded answer and every one of them would become a clarification or a handoff.
3. **Bound clauses for states, open retrieval only for the informational intent, with abstention.** States fetch their clauses by (workflow, state, verified jurisdiction, language); informational questions search the policy text with a measured retriever and abstain below a threshold tuned on held-out judgments.

For the retriever itself: BM25 alone (fast, no model, strong on the catalog's own vocabulary), dense embeddings alone (robust to paraphrase, needs a model the API image does not carry), or reciprocal rank fusion of both.

## Decision

Option 3.

- **Bound lookup.** `WorkflowDescriptor.states` names every state of every workflow; the pack loader rejects bindings that miss a state or name an unknown one, and `BoundPolicyLookup` resolves every state, country, and language at startup, so a missing binding stops the process. The jurisdiction comes from the verified customer record, never from text.
- **Open retrieval.** Only `Intent.INFORMATIONAL` reaches `InformationalRetrieval`, in any workflow. The corpus is the pack's current clauses in the query's language and the customer's jurisdiction (or `ALL`), without the ELG family; the retrieval policy drops ELG hits again. BM25 is implemented in the repository (no maintained, small dependency fits: `rank-bm25` has had no release since 2022, `bm25s` brings SciPy); dense retrieval uses `intfloat/multilingual-e5-small` through sentence-transformers in the optional `ml` extra; hybrid fuses both by reciprocal rank (k = 60) after each component's floor.
- **Measured abstention.** Thresholds are tuned on the dev split of `evals/data/retrieval_judgments.v1.jsonl` (balanced accuracy between answering and abstaining) and reported on the test split, by workflow, language, and jurisdiction ([retrieval evaluation](../evaluation/retrieval.md)).
- **API default: BM25.** The API image never installs the `ml` extra, and on the provisional judgments BM25 has the best abstention recall (1.00 on the test split) at a fraction of a millisecond per query; dense ranks slightly better (recall@3 0.93 against 0.85) but needs the model at query time. `RETRIEVAL_RETRIEVER=dense` or `hybrid` switches with no workflow change once the extra is installed and the labels are reviewed.
- **Index keyed by pack version.** `bank-agent index build` stores indexes under the pack version; the API builds the BM25 index from the loaded pack in development and loads a stored one in production, refusing any mismatch of pack version, corpus digest, tokenizer, or model.
- **Grounding verifier.** Every draft is checked deterministically before a customer sees it (citations, figures, currencies, action claims, balances with their as-of date, catalog figures, eligibility outcomes, approval wording, internal credit figures); any violation sends the workflow to its template (phase 09).

## Consequences

- A decision and its explanation always cite the same clauses at the same versions; a new state needs its binding before the process starts.
- Informational answers can abstain; the abstention rate on in-scope questions is measured (false abstentions) and reported with its sample size.
- The labels are team-written and pending review, and per-workflow test cells hold 12 in-scope queries; the retriever choice is provisional until the review and a larger set.
- The verifier is lexical: paraphrased claims outside its lexicons pass unnoticed, which the template fallback and the evaluation harness (phase 14) must cover.
