# Phase 07 plan: grounding with bound policies and measured retrieval

Status: not a plan-mode phase. The human delegated approvals to the orchestrator, which pre-approved sentence-transformers (with torch) in an optional `ml` extra only, a small multilingual embedding model downloaded from Hugging Face into a gitignored cache, MLflow logging to a local file store (`file:./mlruns`, gitignored), and relevance judgments marked `review_status: pending` with the human review recorded as a pending action. Open questions are decided below with the reasoning. Written against commit `571c781`, after phase 06.

## What already exists

| Piece | State |
|---|---|
| Bound lookup | `PolicyPack.get_bound(workflow, state, jurisdiction, language)` resolves `common` plus state clauses with `{country}`; the loader checks every workflow has its entry state and every resolved clause exists |
| Ports | `Retriever.search(RetrievalQuery) -> RetrievalResult` (hits with `ClauseRef`, score, rank, `ModelRef`); `PolicyRepository` |
| Credit | `EligibilityAssessment`, `RiskEstimate` and `CreditProfile` (fields marked `Internal`), `CreditProduct` catalog entries, `policy.lexicon.approval_terms` |
| CLIs | `bank-agent` (typer) with `db` and `policy`; `bank-eval` with `version` only |

## Files to create or change

| Area | Files |
|---|---|
| Domain | `workflow_catalog.py`: `WorkflowDescriptor.states`, the canonical state names (from `bindings.yaml`); `errors.py`: `RetrievalIndexError`, `RetrievalNotAllowedError` |
| Policy loader | `structure.py`: bindings must cover exactly the registered states of every workflow (a missing binding is a pack load error, so a startup error) |
| `application/grounding/` | `bound.py` (`BoundPolicyLookup`: verifies every state, country, and language at construction; the jurisdiction comes from the verified `Customer`), `retrieval.py` (`RetrievalPolicy`, `InformationalRetrieval`: only the `informational` intent, ELG never returned, threshold abstention), `numbers.py` (es, pt, en number, date, duration, percent normalization), `lexicon.py` (action, balance, total, eligibility, internal-figure terms), `draft.py` (`ResponseDraft`, `GroundingContext`, `RecordFact`, `VerifiedAction`, `Violation`), `verifier.py` (`GroundingVerifier`) |
| `adapters/retrieval/` | `text.py` (accent folding, stopwords, truncation stemming), `corpus.py` (documents from the pack: current clauses, rendered bodies, ELG excluded), `bm25.py`, `embedding.py` (`Embedder` protocol, `SentenceTransformerEmbedder` lazy import, `CachingEmbedder` keyed by content hash), `dense.py`, `hybrid.py` (reciprocal rank fusion), `index_store.py` (build, write, load, and refuse a mismatch), `README.md` |
| Bootstrap | `RetrievalSettings` (`RETRIEVAL_*`), `bootstrap/retrieval.py`, container wiring (bound lookup, verifier, retriever, informational retrieval) |
| CLI | `bank-agent index build` and `make index` |
| Evals | `bank_evals/retrieval/` (judgments model and loader, metrics, runner, threshold tuning, report, MLflow tracker), `bank-eval retrieval`, `make eval-retrieval`, `evals/data/retrieval_judgments.v1.jsonl` |
| Packaging | `bank-agent` extra `ml = [sentence-transformers]`; `mlflow-skinny` in `bank-evals`; torch from the PyTorch CPU index on Linux; `.gitignore` exception for `evals/data/*.jsonl`; mypy overrides |
| Docs | `docs/workflows/grounding.md`, `adapters/retrieval/README.md`, `docs/evaluation/retrieval-labeling.md`, `docs/evaluation/retrieval.md`, ADR 0012, READMEs, indexes, `.env.example`, BACKLOG, PROGRESS |

## Tests to add

- Unit: RRF math; accent folding, stopwords, and truncation; BM25 against a hand-computed example; dense retrieval with a deterministic fake embedder; the embedding cache; jurisdiction and language filtering; index store round trip and mismatch refusals; number, date, duration, and percent tables for es and pt; every verifier case the prompt lists; threshold abstention; the informational-only gate; ELG exclusion; judgments model; metrics (recall@k, MRR, nDCG@5, abstention precision and recall); threshold tuning; report rendering; settings and composition.
- Integration: index build from the real pack (CLI); bound lookup for every state of every workflow, country, and language; loader refuses a pack missing a state binding; retrieval evaluation on the starter judgments end to end (BM25 real, dense and hybrid on the fake embedder, MLflow into `tmp_path`); a real-model test that skips only when the `ml` extra is not installed.

## Decisions on open questions

1. **Where the registered states live.** `WorkflowDescriptor.states` in the domain catalog, equal to the `bindings.yaml` state names. The loader rejects a pack that misses a state (or binds an unknown one), and `BoundPolicyLookup` resolves every state for every country and language at construction. Phase 09 builds its machines from `descriptor.states`.
2. **BM25 implementation.** In-house Okapi BM25 (k1 1.2, b 0.75, non-negative IDF), about 60 lines, unit tested. `rank-bm25` has had no release since 2022 (CLAUDE.md rule 10 asks for maintained dependencies), and `bm25s` pulls SciPy into the API runtime for a corpus of about 140 documents. Recorded in ADR 0012.
3. **Tokenization.** NFKD accent folding, casefold, per-language stopwords (es, pt, en), and prefix truncation to six characters as a light stemmer for Spanish and Portuguese (versioned `fold-stop-trunc6@1`).
4. **ELG and open retrieval.** ELG clauses are excluded from the open-retrieval corpus and dropped again by `RetrievalPolicy`, so retrieved text can never supply an eligibility rule.
5. **Embedding model.** `intfloat/multilingual-e5-small` (MIT, 118M parameters, 384 dimensions, trained for retrieval in about 100 languages, Spanish and Portuguese included) with its `query: ` and `passage: ` prefixes. Cached under `data/models/huggingface` (gitignored); embeddings cached under `data/artifacts/retrieval/embeddings` keyed by a SHA-256 of model, prefix, and text.
6. **Hybrid abstention.** Reciprocal rank scores carry no absolute relevance, so the hybrid retriever fuses only component hits at or above each component's floor (the tuned BM25 and dense thresholds); the policy abstains when nothing survives.
7. **Thresholds without leakage.** Judgments carry `split: dev|test` (stratified by workflow and language). `bank-eval retrieval` tunes thresholds on `dev` (maximizing balanced accuracy between answering in-scope and abstaining out of scope) and reports metrics on `test`; the tuned values are the settings defaults.
8. **API index loading.** `RETRIEVAL_INDEX_SOURCE=build` (default outside production) builds the BM25 index from the loaded pack at startup, so it matches by construction; `stored` loads `<RETRIEVAL_INDEX_DIR>/<pack version>/` and refuses a missing index or a manifest whose pack version, corpus digest, tokenizer, or model differs. Production requires `stored`. The API default retriever is BM25, because the API image never has the `ml` extra.
9. **Verifier scope.** Deterministic and lexical: it checks figures, citations, currency markers, and a closed lexicon of claims. It cannot judge paraphrased claims outside the lexicon; the workflow (phase 09) falls back to templates on any violation.
10. **Judgments path.** The prompt names `evals/data/`; the `**/data/*` ignore rule would hide it, so `.gitignore` gets a narrow exception for `evals/data/*.jsonl`. These are team-written queries, not organizer data.

## Risks

- About 100 judgments split in two leave per-workflow test cells of about 10 queries; every table states its sample size, and the labels are unreviewed.
- The real embedding model is not exercised by `make check` unless the `ml` extra is installed; the fake embedder covers the code path, and the report states which embedder produced each number.
- MLflow's file store is in maintenance mode (MLflow 3.16 raises unless `MLFLOW_ALLOW_FILE_STORE=true`); the tracker sets that flag only for `file:` URIs, as the human asked for the file store.
