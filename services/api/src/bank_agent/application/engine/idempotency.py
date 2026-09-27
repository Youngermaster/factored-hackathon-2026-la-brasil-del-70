"""Idempotency keys for writes, derived from the conversation, the target record, and the action.

The same confirmation of the same action on the same record in the same conversation always yields the same key,
so a retry, a replayed turn, or a step resumed after re-authentication can never write twice; the tools replay
the first outcome for a known key (ADR 0010).
"""

import hashlib

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.identifiers import IdempotencyKey, SourceRef

KEY_PREFIX = "wf-"
DIGEST_LENGTH = 40


def derive_key(conversation_id: str, target: SourceRef, action: ActionKind) -> IdempotencyKey:
    payload = f"{conversation_id}|{target}|{action.value}".encode()
    return IdempotencyKey(KEY_PREFIX + hashlib.sha256(payload).hexdigest()[:DIGEST_LENGTH])
