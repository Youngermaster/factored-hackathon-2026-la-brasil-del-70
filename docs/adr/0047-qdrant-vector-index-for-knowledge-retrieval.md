# 0047: Qdrant vector index for customer-service knowledge retrieval

- Status: Accepted
- Date: 2026-10-05
- Extends: [ADR 0012](0012-bound-policies-and-informational-retrieval.md) (open retrieval for informational
  questions only); related: [ADR 0046](0046-customer-service-history-vector-retrieval.md) (Proposed)

## Context

Informational questions ("how many days do I have to dispute a charge?") are answered by open retrieval over the
customer-facing policy clauses, never by the model's own knowledge (ADR 0012). Production serves BM25 in process.
The dense and hybrid retrievers of phase 07 use `intfloat/multilingual-e5-small`, which needs the optional `ml` extra
(about 806 MB installed, plus a 471 MB model) that the API image never installs, so they were measured but could not
be deployed. Since 2026-10-05 production calls Azure OpenAI, and the same account serves `text-embedding-3-small`.

Constraints:

- One Azure VM with 8 GB of memory and Docker Compose; no Kubernetes.
- Customer text sent to a provider is minimized and redacted (CLAUDE.md rule 6); identifiers never reach a model.
- A retrieval failure must never reach the customer: the workflow already abstains with a clause when nothing
  relevant is found, and BM25 needs no remote service.
- Any switch of the production retriever needs evidence on the relevance judgments, per language.
- A future customer-scoped memory (ADR 0046) must filter by the session's customer, never by a model-supplied value.

## Considered options

1. **Keep BM25 only.** No new service and no provider call. It cannot match a paraphrase that shares no word stem
   with the clause: on the test split its MRR is 0.83 against 0.89 for the Qdrant hybrid, and when the language is
   misdetected (a Spanish query searched against Portuguese clauses) its MRR falls to 0.59 against 0.83 for Qdrant.
2. **Local e5 embeddings in the API image.** No provider call for the query, but the image grows by about 1.3 GB
   and every API worker loads the model into memory on a VM shared with PostgreSQL and the observability stack.
3. **Hosted embeddings with an in-process exact index** (vectors in a file next to the BM25 index). No new service,
   and for today's 123 documents it ranks exactly like a vector store (the evaluation's in-memory store is this
   option). It has no payload index, no persistence across workers beyond a file, and no deletion by filter, so a
   customer-scoped collection (ADR 0046) would need a different design.
4. **pgvector in the existing PostgreSQL.** No new service, and row-level security could guard customer-scoped
   vectors. It needs the extension in the production database image and an owner migration on the system of
   record, and the derived, rebuildable vectors would enter the database backups and its retention rules.
5. **A managed vector service (for example Azure AI Search).** No service to run, but another paid resource,
   another credential, and policy and customer vectors stored outside the VM.
6. **Qdrant as a compose service, with hosted embeddings.** A small, single-binary vector store with payload
   filters, keyword indexes, deletion by filter, and snapshots, on the internal network of the existing VM. It adds
   one container to run and one more dependency to fail, both contained by a profile and a fallback.

## Decision

Option 6, behind a setting that defaults to today's behavior.

- **Service.** `qdrant/qdrant:v1.19.2-unprivileged` pinned by digest, under the `rag` profile of
  `deploy/compose.prod.yml`: uid 1000, read-only root with named volumes for storage and snapshots and tmpfs for
  `/tmp` and the init marker, every capability dropped, no-new-privileges, 0.5 CPU and 512 MB, the internal
  `backend` network only (no egress, no published port), and a readiness health check over bash's `/dev/tcp`
  (the image has no curl or wget). Started only with `RAG=1 deploy/prod.sh up`; releases never wait for it.
- **Adapter.** A `VectorStore` port with six calls and keyword-only filters, implemented over Qdrant's REST API with
  httpx (already a runtime dependency) instead of `qdrant-client`, which would bring gRPC into the image. One shared
  contract suite runs against an in-memory store (unit) and the pinned, hardened image (integration, CI only).
- **Embeddings.** `azure/text-embedding-3-small` at 512 dimensions through LiteLLM's embedding API, behind a new
  `Embedder` gateway with the language model gateway's protections: the query is redacted before it leaves the
  process, then cost accounting (into the shared model-spend metric), a circuit breaker, bounded retry with jitter,
  and a 3 second timeout. The 512 dimensions are a shortened embedding the model supports natively: a third of the
  storage and of the committed recording (634 KB) for a small expected loss that was not measured here.
- **Index.** One collection per pack version and embedding model (`policy-clauses-<pack>-<model>`); one point per
  clause, version, and language with a UUID v5 id of the clause key, so `bank-agent index qdrant` is idempotent;
  a payload of keyword fields only (clause id, version, language, jurisdiction, family, workflow), never the clause
  text, so the pack stays the source of truth. ELG clauses are never indexed, as in ADR 0012.
- **Retrieval.** `RETRIEVAL_RETRIEVER` is `bm25` (default), `qdrant`, or `qdrant_hybrid` (reciprocal rank fusion of
  BM25 and Qdrant, each component kept above its own tuned floor). Filters on language and jurisdiction come from the
  verified session. Any embedding or store failure, an open circuit, or a missing collection answers that query with
  BM25; the result names the retriever that served it and `bank.retrieval.fallbacks` counts it. Retrieval runs in a
  worker thread, so remote calls never block the event loop.
- **Isolation.** No collection is customer-scoped. If one is added (ADR 0046), the session's customer is a mandatory
  filter set by the application from the session context; the model never selects a filter, a collection, or a
  customer.
- **Evidence.** `bank-eval retrieval` compares BM25, e5 dense and hybrid, Qdrant, and Qdrant hybrid on the same
  judgments, per workflow, language, and jurisdiction, plus a cross-language slice. The hosted vectors are a
  committed recording (`evals/data/retrieval_embeddings.text-embedding-3-small-512.v1.jsonl`, hashes only, no
  text), so the evaluation and the tests run offline; re-recording is opt-in on the evaluation account.
- **Switching rule (pre-registered before recording).** Production switches to `qdrant_hybrid` only if, on the test
  split, its MRR is higher than BM25's, its recall at 1, 3, and 5 is not lower in Spanish or in Portuguese, and its
  out-of-scope abstention recall is not lower. The outcome is generated into
  [retrieval.md](../evaluation/retrieval.md).

**Evidence (measured offline on the team-written judgments, pending human review; 48 in-scope and 12 out-of-scope
test queries).** From [retrieval.md](../evaluation/retrieval.md):

| Retriever | R@1 | R@3 | R@5 | MRR | Abstention recall (out of scope) | False abstentions (in scope) |
|---|---|---|---|---|---|---|
| `bm25` (production today) | 0.68 | 0.85 | 0.92 | 0.83 | 1.00 | 0.06 |
| `qdrant` (text-embedding-3-small, 512) | 0.67 | 0.86 | 0.95 | 0.83 | 1.00 | 0.00 |
| `qdrant_hybrid` | 0.76 | 0.90 | 0.95 | 0.89 | 1.00 | 0.00 |
| e5 dense (not deployable, `ml` extra) | 0.69 | 0.93 | 0.95 | 0.86 | 0.92 | 0.02 |

Per language, `qdrant_hybrid` against `bm25`: Spanish R@1 0.69 against 0.64 and MRR 0.86 against 0.81; Portuguese
R@1 0.96 against 0.79 and MRR 1.00 against 0.92 (12 in-scope Portuguese test queries, so one query moves recall by
0.08). Every check of the switching rule passes. Qdrant alone is the most robust to a misdetected language; the
hybrid inherits part of BM25's weakness there (MRR 0.67 from Spanish to Portuguese).

**Second collection: not built.** The task considered a collection of resolved case summaries from the organizer
data. The evidence says there is no usable corpus: 147,292 served transcripts hold 42 distinct customer texts, all
built from two balance questions, and the question does not depend on the contact reason (Cramer's V 0.008;
[workflow evidence](../analysis/workflow-evidence.md)). The committed sample holds 20 transcripts with 11 distinct
customer texts, 5 complaints with 3 distinct descriptions and 1 resolution text, and 16 survey comments with 8
distinct texts. Retrieval over templates would return near-duplicates that say nothing beyond the contact-reason
label, and a customer-scoped collection needs the consent and deletion controls of ADR 0046, which are not built.

## Consequences

- The measured retrieval gain can reach production without the 1.3 GB local model; switching back is one setting.
- One more container, and two more remote dependencies on the informational path. Both fail to BM25, so the
  customer-facing worst case is today's behavior plus the timeout (bounded by the 3 second embedding timeout and the
  2 second store timeout, then an open circuit after five consecutive failures).
- Every informational question sends its redacted text (about 20 tokens) to Azure OpenAI. At the price in
  `services/api/config/llm_prices.yaml` (0.022 USD per million input tokens, Data Zone meter, unverified for the
  Global deployment) that is about 0.44 USD per million questions (projected); indexing the pack costs about 11,000
  tokens once (projected).
- Without a Qdrant API key, every container on the `backend` network can read and write the collections. They hold
  public synthetic policy text only; an API key (staged as a config file, since Qdrant reads no `*_FILE` variable) is
  required before any customer-scoped collection exists.
- The index is derived data: `deploy/prod.sh backup` does not cover it, and `bank-agent index qdrant` rebuilds it.
- The recorded embeddings must be re-recorded (`make eval-retrieval-embeddings`) when the pack or the judgments
  change; a unit test fails until they are.
- The judgments are team-written and pending human review, so the switching rule's outcome is provisional.

## Production delta

What changes on the VM when the retriever is switched on; nothing changes until then.

| Item | Change |
|---|---|
| Containers | `qdrant` (profile `rag`), 512 MB memory limit, two named volumes |
| API environment | `RETRIEVAL_RETRIEVER=qdrant_hybrid`, `RETRIEVAL_QDRANT_URL=http://qdrant:6333` |
| Secrets | none new: the embedding call uses `LLM_API_KEY_PRIMARY` and `LLM_API_BASE` (the same Azure OpenAI account) |
| Azure | the `text-embedding-3-small` deployment of the production account, already present |
| One-time step | `RAG=1 deploy/prod.sh up`, then `bank-agent index qdrant` inside the api container (it has the key and egress; the job network has no egress) |
| Rollback | `RETRIEVAL_RETRIEVER=bm25` and recreate the api service; the `qdrant` container can stay or be stopped |
| Monitoring | `bank.retrieval.fallbacks` (fallback count by error code) and `bank.llm.cost_usd` with `gen_ai.operation.name=embeddings` |
