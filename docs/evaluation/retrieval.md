# Retrieval evaluation

Generated 2026-09-27T15:03:56+00:00 from commit `992fdd6` by `make eval-retrieval`
(`bank-eval retrieval`). Do not edit by hand. The labeling protocol is in
[retrieval-labeling.md](retrieval-labeling.md); the retrieval design is in
[grounding](../workflows/grounding.md).

| Input | Value |
|---|---|
| Judgments | `evals/data/retrieval_judgments.v1.jsonl` (SHA-256 prefix `57ac7ca23214`): 40 dev, 60 test |
| Label review status | pending: 100 |
| Policy pack | `pack-be521e1d5bc3b63f`, 123 documents (ELG clauses excluded) |
| Tokenizer | `fold-stop-trunc6@1` |
| Embedding model | `intfloat/multilingual-e5-small` (sentence-transformers, with its query and passage prefixes) |
| Fusion | reciprocal rank fusion, k = 60, component floors = tuned thresholds |

**Read these numbers with their sample sizes.** Every label is team-written and still pending human review,
so the results are provisional. Each workflow has 12 in-scope test queries, so one query moves a
per-workflow recall by about 0.08; per-language and per-jurisdiction cells are just as small. Ranking
metrics use in-scope queries before the threshold; abstention metrics use the threshold tuned on the dev
split (the hybrid retriever abstains when no component hit clears its floor). Latency is measured in
process on one machine, per query, including the query embedding for dense and hybrid.

## Summary

| Retriever | Model | Threshold | Split | R@1 | R@3 | R@5 | MRR | nDCG@5 | Abst. P | Abst. R | False abst. | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | `retriever:bm25@1` | 3.6292 (tuned on dev) | test | 0.72 | 0.85 | 0.92 | 0.85 | 0.84 | 0.80 | 1.00 | 0.06 | 0.05 | 0.07 |
| bm25 | `retriever:bm25@1` | 3.6292 (tuned on dev) | dev | 0.67 | 0.89 | 0.92 | 0.81 | 0.83 | 0.57 | 1.00 | 0.19 | 0.05 | 0.07 |
| dense | `retriever:dense@intfloat.multilingual-e5-small` | 0.8275 (tuned on dev) | test | 0.69 | 0.93 | 0.95 | 0.86 | 0.86 | 0.92 | 0.92 | 0.02 | 6.47 | 7.57 |
| dense | `retriever:dense@intfloat.multilingual-e5-small` | 0.8275 (tuned on dev) | dev | 0.73 | 0.98 | 1.00 | 0.89 | 0.91 | 1.00 | 1.00 | 0.00 | 6.47 | 7.57 |
| hybrid | `retriever:hybrid@1` | 0.0000 (floors) | test | 0.74 | 0.84 | 0.92 | 0.85 | 0.85 | 0.92 | 0.92 | 0.02 | 6.30 | 6.88 |
| hybrid | `retriever:hybrid@1` | 0.0000 (floors) | dev | 0.83 | 0.97 | 1.00 | 0.93 | 0.94 | 1.00 | 1.00 | 0.00 | 6.30 | 6.88 |

## By workflow (test split)

| Retriever | Slice | In scope | Out of scope | R@1 | R@3 | R@5 | MRR | nDCG@5 | Abst. P | Abst. R | False abst. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | workflow=account_inquiry | 12 | 0 | 0.75 | 0.83 | 0.92 | 0.90 | 0.85 | n/a | n/a | 0.08 |
| bm25 | workflow=card_support | 12 | 0 | 0.75 | 1.00 | 1.00 | 0.96 | 0.92 | n/a | n/a | 0.00 |
| bm25 | workflow=credit | 12 | 0 | 0.83 | 0.92 | 0.92 | 0.86 | 0.88 | n/a | n/a | 0.08 |
| bm25 | workflow=dispute | 12 | 0 | 0.54 | 0.67 | 0.83 | 0.70 | 0.73 | n/a | n/a | 0.08 |
| bm25 | workflow=out_of_scope | 0 | 12 | n/a | n/a | n/a | n/a | n/a | 1.00 | 1.00 | n/a |
| dense | workflow=account_inquiry | 12 | 0 | 0.62 | 0.92 | 0.96 | 0.81 | 0.82 | n/a | n/a | 0.00 |
| dense | workflow=card_support | 12 | 0 | 0.67 | 1.00 | 1.00 | 0.90 | 0.90 | n/a | n/a | 0.00 |
| dense | workflow=credit | 12 | 0 | 0.79 | 0.96 | 1.00 | 0.90 | 0.92 | n/a | n/a | 0.08 |
| dense | workflow=dispute | 12 | 0 | 0.67 | 0.83 | 0.83 | 0.82 | 0.80 | n/a | n/a | 0.00 |
| dense | workflow=out_of_scope | 0 | 12 | n/a | n/a | n/a | n/a | n/a | 1.00 | 0.92 | n/a |
| hybrid | workflow=account_inquiry | 12 | 0 | 0.71 | 0.79 | 0.92 | 0.80 | 0.80 | n/a | n/a | 0.00 |
| hybrid | workflow=card_support | 12 | 0 | 0.75 | 1.00 | 1.00 | 0.96 | 0.94 | n/a | n/a | 0.00 |
| hybrid | workflow=credit | 12 | 0 | 0.83 | 0.92 | 0.92 | 0.88 | 0.89 | n/a | n/a | 0.08 |
| hybrid | workflow=dispute | 12 | 0 | 0.67 | 0.67 | 0.83 | 0.79 | 0.77 | n/a | n/a | 0.00 |
| hybrid | workflow=out_of_scope | 0 | 12 | n/a | n/a | n/a | n/a | n/a | 1.00 | 0.92 | n/a |

## By language (test split)

| Retriever | Slice | In scope | Out of scope | R@1 | R@3 | R@5 | MRR | nDCG@5 | Abst. P | Abst. R | False abst. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | language=es | 36 | 9 | 0.69 | 0.82 | 0.90 | 0.83 | 0.82 | 0.75 | 1.00 | 0.08 |
| bm25 | language=pt | 12 | 3 | 0.79 | 0.96 | 0.96 | 0.92 | 0.92 | 1.00 | 1.00 | 0.00 |
| dense | language=es | 36 | 9 | 0.68 | 0.92 | 0.94 | 0.85 | 0.85 | 0.90 | 1.00 | 0.03 |
| dense | language=pt | 12 | 3 | 0.71 | 0.96 | 0.96 | 0.88 | 0.89 | 1.00 | 0.67 | 0.00 |
| hybrid | language=es | 36 | 9 | 0.69 | 0.81 | 0.90 | 0.82 | 0.81 | 0.90 | 1.00 | 0.03 |
| hybrid | language=pt | 12 | 3 | 0.88 | 0.96 | 0.96 | 0.96 | 0.95 | 1.00 | 0.67 | 0.00 |

## By jurisdiction (test split)

| Retriever | Slice | In scope | Out of scope | R@1 | R@3 | R@5 | MRR | nDCG@5 | Abst. P | Abst. R | False abst. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | jurisdiction=AR | 16 | 4 | 0.72 | 0.81 | 0.88 | 0.80 | 0.80 | 0.80 | 1.00 | 0.06 |
| bm25 | jurisdiction=CO | 16 | 4 | 0.72 | 0.81 | 0.88 | 0.92 | 0.87 | 0.67 | 1.00 | 0.12 |
| bm25 | jurisdiction=MX | 16 | 4 | 0.72 | 0.94 | 1.00 | 0.85 | 0.87 | 1.00 | 1.00 | 0.00 |
| dense | jurisdiction=AR | 16 | 4 | 0.62 | 0.88 | 0.91 | 0.77 | 0.77 | 0.80 | 1.00 | 0.06 |
| dense | jurisdiction=CO | 16 | 4 | 0.66 | 0.91 | 0.94 | 0.90 | 0.88 | 1.00 | 0.75 | 0.00 |
| dense | jurisdiction=MX | 16 | 4 | 0.78 | 1.00 | 1.00 | 0.91 | 0.93 | 1.00 | 1.00 | 0.00 |
| hybrid | jurisdiction=AR | 16 | 4 | 0.66 | 0.75 | 0.84 | 0.75 | 0.74 | 0.80 | 1.00 | 0.06 |
| hybrid | jurisdiction=CO | 16 | 4 | 0.72 | 0.84 | 0.91 | 0.90 | 0.87 | 1.00 | 0.75 | 0.00 |
| hybrid | jurisdiction=MX | 16 | 4 | 0.84 | 0.94 | 1.00 | 0.92 | 0.94 | 1.00 | 1.00 | 0.00 |

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
