# 0046: Customer-service history uses consented vector retrieval

- Status: Proposed
- Date: 2026-09-27 (drafted); 2026-10-05 (renumbered from a draft numbered 0029, a number another record already holds,
  and set to Proposed)

Status note: this record is Proposed, not accepted, because the controls it requires are not built: there is no
customer opt-in, no deletion of a customer's vector points on revocation, and no indexing of resolved conversations.
The policy knowledge base it builds on is accepted and deployable behind a flag
([ADR 0047](0047-qdrant-vector-index-for-knowledge-retrieval.md)); that record also explains, with numbers, why no
second collection from the organizer data is built today.

## Context

The future assistant may need relevant details from a customer's previous service conversations. The chat transcript remains in PostgreSQL; semantic retrieval can find useful passages without sending the full history to the model. This extends the opt-in memory direction in [ADR 0027](0027-opt-in-financial-memory-and-guidance.md), and is deferred beyond the internal MVP completion window ending Sunday, October 4, 2026. The old Tuesday plan in [ADR 0025](0025-tuesday-account-inquiry-mvp-and-observability.md) was superseded.

## Considered options

1. Keep history in PostgreSQL and search by exact terms; simple, but misses paraphrases and related context.
2. Copy full transcripts into a vector database; easy to retrieve, but duplicates sensitive content and weakens the source-of-truth boundary.
3. Index consented, redacted conversation chunks in a Qdrant-like vector store behind an adapter; supports semantic retrieval while keeping PostgreSQL authoritative and allowing the vector index to be rebuilt.

## Decision

Use option 3 as a future, opt-in memory capability, on the vector store adapter that
[ADR 0047](0047-qdrant-vector-index-for-knowledge-retrieval.md) introduces. Persist transcripts and messages in PostgreSQL. Build a derived vector index from resolved, consented service conversations; use the stored source references to retrieve the original approved text when needed. The vector database is an index, never the authoritative conversation store.

### Vector payload JSON Schema

The vector is stored separately from this payload. Reject undeclared fields and validate every payload against this versioned schema before indexing.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "customer-service-memory-chunk-v1.schema.json",
  "title": "CustomerServiceMemoryChunk",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "memory_id",
    "customer_ref",
    "conversation_id",
    "message_ids",
    "workflow",
    "language",
    "chunk_text_redacted",
    "resolved_at",
    "consent_ref",
    "embedding_model",
    "embedding_version"
  ],
  "properties": {
    "schema_version": {
      "const": "1.0"
    },
    "memory_id": {
      "type": "string",
      "format": "uuid"
    },
    "customer_ref": {
      "type": "string",
      "minLength": 1,
      "description": "Pseudonymous customer key used for mandatory tenant filtering."
    },
    "conversation_id": {
      "type": "string",
      "format": "uuid"
    },
    "message_ids": {
      "type": "array",
      "minItems": 1,
      "uniqueItems": true,
      "items": {
        "type": "string",
        "format": "uuid"
      }
    },
    "workflow": {
      "enum": [
        "account_inquiry",
        "card_support",
        "dispute",
        "credit"
      ]
    },
    "language": {
      "type": "string",
      "pattern": "^[a-z]{2}(-[A-Z]{2})?$"
    },
    "chunk_text_redacted": {
      "type": "string",
      "minLength": 1,
      "maxLength": 4000,
      "description": "Approved, redacted conversation text or a sourced summary."
    },
    "resolved_at": {
      "type": "string",
      "format": "date-time"
    },
    "consent_ref": {
      "type": "string",
      "minLength": 1
    },
    "embedding_model": {
      "type": "string",
      "minLength": 1
    },
    "embedding_version": {
      "type": "string",
      "minLength": 1
    }
  }
}
```

### Retrieval and controls

- Require explicit customer opt-in before creating or searching this memory. Enforce the customer filter in the backend on every query; never rely on a model-supplied customer reference.
- Redact sensitive identifiers before embedding. Index only resolved conversations and the minimum useful text; do not store credentials, full account/card numbers, or unredacted transcripts in the vector payload.
- Treat retrieved text as untrusted evidence, not instructions. Give the model source conversation/message references and dates; it must distinguish past statements from current account facts and disclose when history may be stale.
- Revoking consent deletes the customer's vector points and stops future indexing/retrieval. PostgreSQL retains the transcript according to its separate retention policy. Rebuild the vector index from eligible PostgreSQL records when the schema or embedding model changes.
- Trace retrieval with correlation ID, customer reference, memory IDs, source IDs, schema version, embedding model/version, and retrieval outcome. Do not put retrieved raw text into observability traces unless it passes the redaction boundary.

## Consequences

- Retrieval can surface prior context across paraphrased service requests, while PostgreSQL remains the audit record and source of truth.
- Consent, deletion, filtering, redaction, schema migration, and embedding-version management are required before this capability ships.
- Retrieval may return stale or irrelevant history; the assistant must source its claims and ask, abstain, or hand off when the retrieved context is not enough.

## References

- [ADR 0047: Qdrant vector index for customer-service knowledge retrieval](0047-qdrant-vector-index-for-knowledge-retrieval.md)
- [ADR 0025: superseded historical Tuesday MVP and observability plan](0025-tuesday-account-inquiry-mvp-and-observability.md)
- [ADR 0027: Financial memory and guidance are opt-in and grounded](0027-opt-in-financial-memory-and-guidance.md)
- [Data card: intended use and data boundaries](../data/data-card.md)
