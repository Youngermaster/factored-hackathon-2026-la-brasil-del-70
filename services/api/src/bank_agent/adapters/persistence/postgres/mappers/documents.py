"""Domain documents stored as JSONB, with a canonical form and a content digest.

The canonical form is the model's JSON-mode dump serialized with sorted keys and no whitespace, so the same
document always has the same digest. Reading a document back validates it through the domain model, so a
row that no longer satisfies the model fails loudly instead of flowing into the service.
"""

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def document_of(model: BaseModel) -> dict[str, Any]:
    """The JSON-mode dump stored in a ``document`` column."""
    dumped: dict[str, Any] = model.model_dump(mode="json")
    return dumped


def canonical_json(document: dict[str, Any]) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_digest(model: BaseModel) -> str:
    """SHA-256 hex digest of the canonical document."""
    return hashlib.sha256(canonical_json(document_of(model)).encode("utf-8")).hexdigest()


def load_document[M: BaseModel](model_type: type[M], value: object) -> M:
    """Validate a stored document (asyncpg returns JSONB as text unless a codec is registered)."""
    if isinstance(value, str | bytes):
        return model_type.model_validate_json(value)
    return model_type.model_validate(value)


def json_object(value: object) -> dict[str, Any]:
    """A stored JSONB object as a dictionary."""
    loaded = json.loads(value) if isinstance(value, str | bytes) else value
    if not isinstance(loaded, dict):
        raise TypeError("a stored document must be a JSON object")
    return loaded
