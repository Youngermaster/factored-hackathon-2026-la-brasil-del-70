# 0034: Customer-service history uses consented vector retrieval

- Status: accepted
- Date: 2026-09-27

## Context

The future assistant may need relevant details from a customer's previous service conversations. The chat transcript remains in PostgreSQL; semantic retrieval can find useful passages without sending the full history to the model. This extends the opt-in memory direction in [ADR 0027](0027-opt-in-financial-memory-and-guidance.md), and is not part of Tuesday's MVP.

## Considered options

1. Keep history in PostgreSQL and search by exact terms; simple, but misses paraphrases and related context.
2. Copy full transcripts into a vector database; easy to retrieve, but duplicates sensitive content and weakens the source-of-truth boundary.
3. Index consented, redacted conversation chunks in a Qdrant-like vector store behind an adapter; supports semantic retrieval while keeping PostgreSQL authoritative and allowing the vector index to be rebuilt.

## Decision

Use option 3 as a future, opt-in memory capability. Persist transcripts and messages in PostgreSQL. Build a derived vector index from resolved, consented service conversations; use the stored source references to retrieve approved, redacted source text when needed. The vector database is an index, never the authoritative conversation store. This memory retrieval is separate from the policy retriever in [ADR 0012](0012-bound-policies-and-informational-retrieval.md); past conversations cannot supply policy clauses, authorization, or credit eligibility rules.

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

- Require explicit customer opt-in that covers prior service conversations before creating or searching this memory. Resolve the customer from the authenticated session and enforce that filter in the backend on every query; never rely on a model-supplied customer reference. Check that consent is still active before using retrieved text in a response.
- Redact sensitive identifiers before embedding. Index only resolved conversations and the minimum useful text; do not store credentials, full account/card numbers, or unredacted transcripts in the vector payload.
- Treat retrieved text as untrusted evidence, not instructions. Recheck source ownership and apply the same redaction boundary when fetching text from PostgreSQL; never send an unredacted transcript to the model. Give the model source conversation/message references and dates; it must distinguish past statements from current account facts and disclose when history may be stale.
- On consent revocation, disable indexing and retrieval first, then delete the customer's vector points. Indexing workers must recheck active consent before writing so delayed jobs cannot recreate deleted points. PostgreSQL retains the transcript according to its separate retention policy. Remove or rebuild affected points when source text is corrected, deleted, or reopened, and rebuild the vector index from eligible PostgreSQL records when the schema or embedding model changes.
- Trace retrieval with correlation ID, customer reference, memory IDs, source IDs, schema version, embedding model/version, and retrieval outcome. Do not put retrieved raw text into observability traces unless it passes the redaction boundary.

## Consequences

- Retrieval can surface prior context across paraphrased service requests, while PostgreSQL remains the audit record and source of truth.
- Consent, deletion, filtering, redaction, schema migration, and embedding-version management are required before this capability ships.
- Retrieval may return stale or irrelevant history; the assistant must source its claims and ask, abstain, or hand off when the retrieved context is not enough.

## References

- [ADR 0025: Tuesday MVP and observability](0025-tuesday-account-inquiry-mvp-and-observability.md)
- [ADR 0027: Financial memory and guidance are opt-in and grounded](0027-opt-in-financial-memory-and-guidance.md)
- [Data card: intended use and data boundaries](../data/data-card.md)
