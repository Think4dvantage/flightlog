"""Pydantic schemas for pilot-managed API keys (v0.8)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# A short, explicit list of named capabilities — not a generic roles/permissions system
# (spec.md's Assumptions).
VALID_SCOPES = {"flights:read", "flight_links:write"}


class ApiKeyCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(..., min_length=1)
    expires_at: datetime | None = None

    @field_validator("scopes")
    @classmethod
    def _validate_scopes(cls, v: list[str]) -> list[str]:
        unknown = set(v) - VALID_SCOPES
        if unknown:
            raise ValueError(f"Unknown scope(s): {', '.join(sorted(unknown))}")
        return v


class ApiKeyOut(BaseModel):
    """Never carries a live key value — key_hash and the plaintext are never serialised."""

    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreateOut(ApiKeyOut):
    """The one and only response that ever carries the full plaintext key."""

    key: str
