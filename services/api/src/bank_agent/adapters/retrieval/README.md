# bank_agent.adapters.retrieval

## Responsibility

Open retrieval over the synthetic policy pack for informational questions, behind the `Retriever` port. It builds the corpus from the pack's current clauses (never the ELG family), scores it with BM25, dense embeddings, or their fusion, and stores indexes keyed by the pack version. It never holds customer data, and it never decides whether to answer: the application's `RetrievalPolicy` applies the threshold ([grounding](../../../../../../docs/workflows/grounding.md)).

## Public interfaces

| Module | Interface |
|---|---|
| `text.py` | `fold`, `tokenize(text, language)`, `TOKENIZER_VERSION` (`fold-stop-trunc6@1`) |
| `corpus.py` | `ClauseDocument` (`visible_to(language, jurisdiction)`), `build_corpus(repository)`, `corpus_digest`, `EXCLUDED_FAMILIES` |
| `bm25.py` | `Bm25Index` (build, payload round trip), `Bm25Retriever`, model `retriever:bm25@1` |
| `embedding.py` | `Embedder` protocol, `SentenceTransformerEmbedder` (optional `ml` extra, lazy import), `CachingEmbedder` (one JSON file per text, named by a SHA-256 of model, kind, and text), `ml_extra_installed()` |
| `dense.py` | `DenseIndex`, `DenseRetriever`, model `retriever:dense@<embedding model>` |
| `hybrid.py` | `HybridRetriever` over `FusionComponent(retriever, floor)` with reciprocal rank fusion, model `retriever:hybrid@1` |
| `ranking.py` | `rank_hits`, `reciprocal_rank_fusion(rankings, k)` |
| `index_store.py` | `build_index`, `write_index`, `load_index` (refuses another pack version, corpus, tokenizer, or model), `IndexManifest` |

Every retriever filters by the query's language and jurisdiction (plus `ALL`) before scoring, returns hits best first with ties broken by clause key, and identifies itself with a `ModelRef`.

## Dependencies

- BM25 is implemented here: `rank-bm25` has had no release since 2022, and `bm25s` brings SciPy into the API runtime for a corpus of about 140 documents.
- sentence-transformers 6.1.0 with torch 2.14.0 is the optional `ml` extra of `bank-agent` (about 806 MB installed with transformers, SciPy, and scikit-learn; torch comes from the PyTorch CPU index on Linux). The API image never installs it. Install it with `uv sync --all-packages --extra ml`.
- The model `intfloat/multilingual-e5-small` (MIT) downloads from Hugging Face into `data/models/huggingface` (about 471 MB, gitignored) on first use; embeddings are cached under `data/artifacts/retrieval/embeddings`.

## How to re-index

```bash
make index                      # BM25 only, under data/artifacts/retrieval/indexes/<pack version>/
make index DENSE=1              # also embed every clause (needs the ml extra)
uv run bank-agent index build --help
```

Re-index after any pack change: the pack version changes with any clause, binding, or catalog edit, and an API started with `RETRIEVAL_INDEX_SOURCE=stored` refuses an index built for another version. Development (`RETRIEVAL_INDEX_SOURCE=build`, the default) builds the BM25 index from the loaded pack at startup. Changing the tokenizer lists or the prefix length requires a new `TOKENIZER_VERSION`.

## How to add a retriever

1. Implement `search(query: RetrievalQuery) -> RetrievalResult` with a `model: ModelRef` attribute (component `retriever`, a new name), filtering with `ClauseDocument.visible_to` before scoring and ranking with `rank_hits`.
2. If it needs stored state, add it to `RetrievalIndex` and `IndexManifest`, write and load it in `index_store.py`, and refuse a mismatch on load.
3. Add a threshold for its name in `bootstrap/retrieval.py` (`retrieval_policy`) and a `RETRIEVAL_*` setting, and select it in `build_retriever`.
4. Add it to `bank_evals.retrieval.evaluation.evaluate`, run `make eval-retrieval`, and tune its threshold on the dev split only.
5. Unit tests with the fixture documents and `HashingEmbedder` in `services/api/tests/bank_agent_retrieval.py`; an integration test over the real pack.

## How to test

```bash
uv run pytest services/api/tests/unit/adapters/retrieval -q          # tokenizer, BM25 formula, fusion, dense, cache, index store
uv run pytest services/api/tests/integration/grounding -q            # real pack, composition, CLI; real model only with the ml extra
```

Unit tests never download a model: they use the deterministic `HashingEmbedder`. `test_real_embedding_model.py` runs the real model and is skipped, with its reason, only when the `ml` extra is not installed.
