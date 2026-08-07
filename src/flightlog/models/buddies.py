"""Pydantic schemas for buddies (flying contacts) and the two-sided account-link flow."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class BuddyCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=80)


class BuddyUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=80)


class BuddyOut(BaseModel):
    id: str
    owner_id: str
    display_name: str
    linked_user_id: str | None
    link_state: Literal["none", "pending", "confirmed", "declined"]
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BuddyLinkRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, v: str) -> str:
        return v.lower().strip()
