"""Base classes for request and response models."""

from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    """Request bodies: unknown keys are rejected, and string fields accept only JSON strings.

    Numbers are never coerced to text. Model-wide strict mode is not used because FastAPI validates decoded JSON,
    where strict mode would refuse enums and UUIDs in their JSON string form.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=False, coerce_numbers_to_str=False)


class ResponseModel(BaseModel):
    """Response bodies built from domain objects by attribute; attributes they do not name are ignored."""

    model_config = ConfigDict(extra="ignore", from_attributes=True, frozen=True)
