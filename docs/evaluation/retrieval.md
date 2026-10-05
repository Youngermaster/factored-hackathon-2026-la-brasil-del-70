# Retrieval evaluation

Generated 2026-10-05T17:34:09+00:00 from commit `0b7fd86` by `make eval-retrieval`
(`bank-eval retrieval`). Do not edit by hand. The labeling protocol is in
[retrieval-labeling.md](retrieval-labeling.md); the retrieval design is in
[grounding](../workflows/grounding.md).

| Input | Value |
|---|---|
| Judgments | `evals/data/retrieval_judgments.v1.jsonl` (SHA-256 prefix `57ac7ca23214`): 40 dev, 60 test |
| Label review status | pending: 100 |
| Policy pack | `pack-5ee486a3be987025`, 123 documents (ELG clauses excluded) |
| Tokenizer | `fold-stop-trunc6@1` |
| Embedding model | `intfloat/multilingual-e5-small` (sentence-transformers, with its query and passage prefixes) |
| Hosted embeddings (Qdrant) | `azure/text-embedding-3-small` at 512 dimensions, from `evals/data/retrieval_embeddings.text-embedding-3-small-512.v1.jsonl`, recorded 2026-10-05T16:27:12+00:00 (queries redacted as in production); store `InMemoryVectorStore` |
| Fusion | reciprocal rank fusion, k = 60, component floors = tuned thresholds |

**Read these numbers with their sample sizes.** Every label is team-written and still pending human review,
so the results are provisional. Each workflow has 12 in-scope test queries, so one query moves a
per-workflow recall by about 0.08; per-language and per-jurisdiction cells are just as small. Ranking
metrics use in-scope queries before the threshold; abstention metrics use the threshold tuned on the dev
split (the hybrid retrievers abstain when no component hit clears its floor). Latency is measured in
process on one machine, per query, including the query embedding for dense and hybrid; for `qdrant` and
`qdrant_hybrid` the vectors are replayed from the recording and the store is in process, so their latency
excludes the embedding call and the network (offline measurement, not a production latency).

## Summary

| Retriever | Model | Threshold | Split | R@1 | R@3 | R@5 | MRR | nDCG@5 | Abst. P | Abst. R | False abst. | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | `retriever:bm25@1` | 3.5738 (tuned on dev) | test | 0.68 | 0.85 | 0.92 | 0.83 | 0.83 | 0.80 | 1.00 | 0.06 | 0.12 | 0.16 |
| bm25 | `retriever:bm25@1` | 3.5738 (tuned on dev) | dev | 0.66 | 0.92 | 0.92 | 0.80 | 0.83 | 0.57 | 1.00 | 0.19 | 0.12 | 0.16 |
| dense | `retriever:dense@intfloat.multilingual-e5-small` | 0.8275 (tuned on dev) | test | 0.69 | 0.93 | 0.95 | 0.86 | 0.86 | 0.92 | 0.92 | 0.02 | 15.58 | 20.42 |
| dense | `retriever:dense@intfloat.multilingual-e5-small` | 0.8275 (tuned on dev) | dev | 0.73 | 0.98 | 1.00 | 0.89 | 0.91 | 1.00 | 1.00 | 0.00 | 15.58 | 20.42 |
| hybrid | `retriever:hybrid@1` | 0.0000 (floors) | test | 0.72 | 0.86 | 0.92 | 0.85 | 0.84 | 0.92 | 0.92 | 0.02 | 16.07 | 24.31 |
| hybrid | `retriever:hybrid@1` | 0.0000 (floors) | dev | 0.81 | 0.97 | 1.00 | 0.92 | 0.94 | 1.00 | 1.00 | 0.00 | 16.07 | 24.31 |
| qdrant | `retriever:qdrant@azure.text-embedding-3-small.512` | 0.4618 (tuned on dev) | test | 0.67 | 0.86 | 0.95 | 0.83 | 0.84 | 1.00 | 1.00 | 0.00 | 1.03 | 1.40 |
| qdrant | `retriever:qdrant@azure.text-embedding-3-small.512` | 0.4618 (tuned on dev) | dev | 0.69 | 0.91 | 0.94 | 0.85 | 0.86 | 1.00 | 1.00 | 0.00 | 1.03 | 1.40 |
| qdrant_hybrid | `retriever:hybrid@bm25-qdrant.azure.text-embedding-3-small.512` | 0.0000 (floors) | test | 0.76 | 0.90 | 0.95 | 0.89 | 0.88 | 1.00 | 1.00 | 0.00 | 1.28 | 1.64 |
| qdrant_hybrid | `retriever:hybrid@bm25-qdrant.azure.text-embedding-3-small.512` | 0.0000 (floors) | dev | 0.75 | 0.97 | 0.97 | 0.88 | 0.90 | 1.00 | 1.00 | 0.00 | 1.28 | 1.64 |

## By workflow (test split)

| Retriever | Slice | In scope | Out of scope | R@1 | R@3 | R@5 | MRR | nDCG@5 | Abst. P | Abst. R | False abst. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | workflow=account_inquiry | 12 | 0 | 0.75 | 0.83 | 0.92 | 0.90 | 0.85 | n/a | n/a | 0.08 |
| bm25 | workflow=card_support | 12 | 0 | 0.75 | 1.00 | 1.00 | 0.96 | 0.92 | n/a | n/a | 0.00 |
| bm25 | workflow=credit | 12 | 0 | 0.83 | 0.92 | 0.92 | 0.86 | 0.88 | n/a | n/a | 0.08 |
| bm25 | workflow=dispute | 12 | 0 | 0.38 | 0.67 | 0.83 | 0.62 | 0.67 | n/a | n/a | 0.08 |
| bm25 | workflow=out_of_scope | 0 | 12 | n/a | n/a | n/a | n/a | n/a | 1.00 | 1.00 | n/a |
| dense | workflow=account_inquiry | 12 | 0 | 0.62 | 0.92 | 0.96 | 0.81 | 0.82 | n/a | n/a | 0.00 |
| dense | workflow=card_support | 12 | 0 | 0.67 | 1.00 | 1.00 | 0.90 | 0.90 | n/a | n/a | 0.00 |
| dense | workflow=credit | 12 | 0 | 0.79 | 0.96 | 1.00 | 0.90 | 0.92 | n/a | n/a | 0.08 |
| dense | workflow=dispute | 12 | 0 | 0.67 | 0.83 | 0.83 | 0.82 | 0.80 | n/a | n/a | 0.00 |
| dense | workflow=out_of_scope | 0 | 12 | n/a | n/a | n/a | n/a | n/a | 1.00 | 0.92 | n/a |
| hybrid | workflow=account_inquiry | 12 | 0 | 0.71 | 0.79 | 0.92 | 0.80 | 0.80 | n/a | n/a | 0.00 |
| hybrid | workflow=card_support | 12 | 0 | 0.75 | 1.00 | 1.00 | 0.96 | 0.94 | n/a | n/a | 0.00 |
| hybrid | workflow=credit | 12 | 0 | 0.83 | 0.92 | 0.92 | 0.88 | 0.89 | n/a | n/a | 0.08 |
| hybrid | workflow=dispute | 12 | 0 | 0.58 | 0.75 | 0.83 | 0.75 | 0.75 | n/a | n/a | 0.00 |
| hybrid | workflow=out_of_scope | 0 | 12 | n/a | n/a | n/a | n/a | n/a | 1.00 | 0.92 | n/a |
| qdrant | workflow=account_inquiry | 12 | 0 | 0.75 | 0.79 | 0.88 | 0.85 | 0.84 | n/a | n/a | 0.00 |
| qdrant | workflow=card_support | 12 | 0 | 0.71 | 1.00 | 1.00 | 0.92 | 0.93 | n/a | n/a | 0.00 |
| qdrant | workflow=credit | 12 | 0 | 0.54 | 0.83 | 1.00 | 0.73 | 0.77 | n/a | n/a | 0.00 |
| qdrant | workflow=dispute | 12 | 0 | 0.67 | 0.83 | 0.92 | 0.82 | 0.83 | n/a | n/a | 0.00 |
| qdrant | workflow=out_of_scope | 0 | 12 | n/a | n/a | n/a | n/a | n/a | 1.00 | 1.00 | n/a |
| qdrant_hybrid | workflow=account_inquiry | 12 | 0 | 0.75 | 0.79 | 0.88 | 0.85 | 0.83 | n/a | n/a | 0.00 |
| qdrant_hybrid | workflow=card_support | 12 | 0 | 0.83 | 1.00 | 1.00 | 1.00 | 0.97 | n/a | n/a | 0.00 |
| qdrant_hybrid | workflow=credit | 12 | 0 | 0.88 | 1.00 | 1.00 | 0.96 | 0.94 | n/a | n/a | 0.00 |
| qdrant_hybrid | workflow=dispute | 12 | 0 | 0.58 | 0.79 | 0.92 | 0.77 | 0.79 | n/a | n/a | 0.00 |
| qdrant_hybrid | workflow=out_of_scope | 0 | 12 | n/a | n/a | n/a | n/a | n/a | 1.00 | 1.00 | n/a |

## By language (test split)

| Retriever | Slice | In scope | Out of scope | R@1 | R@3 | R@5 | MRR | nDCG@5 | Abst. P | Abst. R | False abst. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | language=es | 36 | 9 | 0.64 | 0.82 | 0.90 | 0.81 | 0.80 | 0.75 | 1.00 | 0.08 |
| bm25 | language=pt | 12 | 3 | 0.79 | 0.96 | 0.96 | 0.92 | 0.92 | 1.00 | 1.00 | 0.00 |
| dense | language=es | 36 | 9 | 0.68 | 0.92 | 0.94 | 0.85 | 0.85 | 0.90 | 1.00 | 0.03 |
| dense | language=pt | 12 | 3 | 0.71 | 0.96 | 0.96 | 0.88 | 0.89 | 1.00 | 0.67 | 0.00 |
| hybrid | language=es | 36 | 9 | 0.67 | 0.83 | 0.90 | 0.81 | 0.81 | 0.90 | 1.00 | 0.03 |
| hybrid | language=pt | 12 | 3 | 0.88 | 0.96 | 0.96 | 0.96 | 0.95 | 1.00 | 0.67 | 0.00 |
| qdrant | language=es | 36 | 9 | 0.62 | 0.85 | 0.93 | 0.81 | 0.82 | 1.00 | 1.00 | 0.00 |
| qdrant | language=pt | 12 | 3 | 0.79 | 0.92 | 1.00 | 0.89 | 0.92 | 1.00 | 1.00 | 0.00 |
| qdrant_hybrid | language=es | 36 | 9 | 0.69 | 0.86 | 0.93 | 0.86 | 0.84 | 1.00 | 1.00 | 0.00 |
| qdrant_hybrid | language=pt | 12 | 3 | 0.96 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 |

## By jurisdiction (test split)

| Retriever | Slice | In scope | Out of scope | R@1 | R@3 | R@5 | MRR | nDCG@5 | Abst. P | Abst. R | False abst. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | jurisdiction=AR | 16 | 4 | 0.66 | 0.81 | 0.88 | 0.77 | 0.77 | 0.80 | 1.00 | 0.06 |
| bm25 | jurisdiction=CO | 16 | 4 | 0.66 | 0.81 | 0.88 | 0.89 | 0.84 | 0.67 | 1.00 | 0.12 |
| bm25 | jurisdiction=MX | 16 | 4 | 0.72 | 0.94 | 1.00 | 0.85 | 0.87 | 1.00 | 1.00 | 0.00 |
| dense | jurisdiction=AR | 16 | 4 | 0.62 | 0.88 | 0.91 | 0.77 | 0.77 | 0.80 | 1.00 | 0.06 |
| dense | jurisdiction=CO | 16 | 4 | 0.66 | 0.91 | 0.94 | 0.90 | 0.88 | 1.00 | 0.75 | 0.00 |
| dense | jurisdiction=MX | 16 | 4 | 0.78 | 1.00 | 1.00 | 0.91 | 0.93 | 1.00 | 1.00 | 0.00 |
| hybrid | jurisdiction=AR | 16 | 4 | 0.59 | 0.75 | 0.84 | 0.72 | 0.72 | 0.80 | 1.00 | 0.06 |
| hybrid | jurisdiction=CO | 16 | 4 | 0.72 | 0.84 | 0.91 | 0.90 | 0.87 | 1.00 | 0.75 | 0.00 |
| hybrid | jurisdiction=MX | 16 | 4 | 0.84 | 1.00 | 1.00 | 0.93 | 0.95 | 1.00 | 1.00 | 0.00 |
| qdrant | jurisdiction=AR | 16 | 4 | 0.66 | 0.81 | 0.94 | 0.79 | 0.80 | 1.00 | 1.00 | 0.00 |
| qdrant | jurisdiction=CO | 16 | 4 | 0.56 | 0.91 | 0.91 | 0.83 | 0.83 | 1.00 | 1.00 | 0.00 |
| qdrant | jurisdiction=MX | 16 | 4 | 0.78 | 0.88 | 1.00 | 0.87 | 0.90 | 1.00 | 1.00 | 0.00 |
| qdrant_hybrid | jurisdiction=AR | 16 | 4 | 0.69 | 0.88 | 0.94 | 0.82 | 0.81 | 1.00 | 1.00 | 0.00 |
| qdrant_hybrid | jurisdiction=CO | 16 | 4 | 0.69 | 0.88 | 0.91 | 0.91 | 0.88 | 1.00 | 1.00 | 0.00 |
| qdrant_hybrid | jurisdiction=MX | 16 | 4 | 0.91 | 0.94 | 1.00 | 0.95 | 0.96 | 1.00 | 1.00 | 0.00 |

## Cross-language (test split)

Each in-scope test query searched against the other language's documents (the same clause ids exist in both languages, so the labels carry over): what a customer gets when the language detector picks the wrong language. Production filters by the detected language, so this measures robustness, not the normal path.

| Retriever | Slice | In scope | Out of scope | R@1 | R@3 | R@5 | MRR | nDCG@5 | Abst. P | Abst. R | False abst. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | cross_language=es_to_pt | 36 | 0 | 0.43 | 0.61 | 0.71 | 0.59 | 0.59 | n/a | n/a | 0.64 |
| bm25 | cross_language=pt_to_es | 12 | 0 | 0.62 | 0.79 | 0.88 | 0.74 | 0.77 | n/a | n/a | 0.42 |
| dense | cross_language=es_to_pt | 36 | 0 | 0.74 | 0.88 | 0.93 | 0.90 | 0.86 | n/a | n/a | 0.42 |
| dense | cross_language=pt_to_es | 12 | 0 | 0.79 | 0.96 | 1.00 | 0.92 | 0.93 | n/a | n/a | 0.17 |
| hybrid | cross_language=es_to_pt | 36 | 0 | 0.47 | 0.58 | 0.60 | 0.58 | 0.55 | n/a | n/a | 0.31 |
| hybrid | cross_language=pt_to_es | 12 | 0 | 0.88 | 0.88 | 0.92 | 0.92 | 0.91 | n/a | n/a | 0.08 |
| qdrant | cross_language=es_to_pt | 36 | 0 | 0.68 | 0.82 | 0.90 | 0.83 | 0.82 | n/a | n/a | 0.33 |
| qdrant | cross_language=pt_to_es | 12 | 0 | 0.71 | 0.83 | 1.00 | 0.83 | 0.87 | n/a | n/a | 0.17 |
| qdrant_hybrid | cross_language=es_to_pt | 36 | 0 | 0.56 | 0.67 | 0.67 | 0.67 | 0.63 | n/a | n/a | 0.28 |
| qdrant_hybrid | cross_language=pt_to_es | 12 | 0 | 0.79 | 0.83 | 0.83 | 0.83 | 0.83 | n/a | n/a | 0.08 |

## Sample sizes

| Split and workflow | Queries |
|---|---|
| dev.account_inquiry | 8 |
| dev.card_support | 8 |
| dev.credit | 8 |
| dev.dispute | 8 |
| dev.out_of_scope | 8 |
| test.account_inquiry | 12 |
| test.card_support | 12 |
| test.credit | 12 |
| test.dispute | 12 |
| test.out_of_scope | 12 |

## Production decision (pre-registered rule)

Registered on 2026-10-05, before the hosted embeddings were recorded (`evals/src/bank_evals/retrieval/decision.py`): production switches from `bm25` to `qdrant_hybrid` only if,
on the test split, it has a higher MRR, its recall at 1, 3, and 5 is not lower in Spanish or in Portuguese,
and (a safety guard added at registration) its out-of-scope abstention recall is not lower.

| Check | qdrant_hybrid | bm25 | Passed |
|---|---|---|---|
| test MRR is higher | 0.89 | 0.83 | yes |
| es recall@1 is not lower | 0.69 | 0.64 | yes |
| es recall@3 is not lower | 0.86 | 0.82 | yes |
| es recall@5 is not lower | 0.93 | 0.90 | yes |
| pt recall@1 is not lower | 0.96 | 0.79 | yes |
| pt recall@3 is not lower | 1.00 | 0.96 | yes |
| pt recall@5 is not lower | 1.00 | 0.96 | yes |
| out-of-scope abstention recall is not lower | 1.00 | 1.00 | yes |

**Outcome: the rule passes: switch to `qdrant_hybrid`.** The labels are pending human review (see above).

## Decision and discussion (hand-written)

The text between the markers below is kept when the report is regenerated.

<!-- hand-written:start -->
**Decision (2026-10-05): switch production to `qdrant_hybrid`, provisionally.** The rule registered before the
hosted embeddings were recorded passes: on the test split `qdrant_hybrid` has a higher MRR than `bm25` (0.89
against 0.83), loses no recall at 1, 3, or 5 in Spanish or in Portuguese, abstains on every out-of-scope query as
BM25 does, and wrongly abstains on no in-scope query (BM25: 0.06). The switch is one setting
(`RETRIEVAL_RETRIEVER`), with BM25 as the automatic fallback and the rollback ([ADR 0047](../adr/0047-qdrant-vector-index-for-knowledge-retrieval.md)).

Conditions and caveats:

- The labels are team-written and pending human review. The Portuguese cells hold 12 in-scope test queries, so the
  Portuguese gain at rank 1 (0.96 against 0.79) is two queries. When the reviewed `v2` judgments exist, the rule is
  run again and decides again.
- Production fuses with the BM25 floor from settings (3.6292, tuned on an earlier pack version); this run tuned
  3.5738 on the current pack. Hits with a BM25 score between the two enter the fusion here but not in production
  (recorded in `docs/BACKLOG.md`).
- The latency columns of `qdrant` and `qdrant_hybrid` exclude the embedding call and the network (offline
  measurement). The production cost of the switch is one embedding call per informational question, bounded by a
  3 second timeout; it is measured on the VM after the switch, not here.
- Qdrant alone is the most robust to a misdetected language (MRR 0.83 against 0.59 for BM25 from Spanish queries to
  Portuguese clauses); the hybrid keeps part of BM25's weakness there (0.67). Production filters by the detected
  language, so this matters only when detection fails.
- The e5 retrievers stay as a reference: they need the `ml` extra, which the API image never installs.
<!-- hand-written:end -->
