"""Pydantic schemas for gliders."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GliderCreate(BaseModel):
    brand: str = Field(..., min_length=1, max_length=80)
    model: str = Field(..., min_length=1, max_length=80)
    size: str | None = None
    nickname: str | None = None
    en_class: str | None = None
    is_own: bool = True


class GliderUpdate(BaseModel):
    brand: str | None = Field(None, min_length=1, max_length=80)
    model: str | None = Field(None, min_length=1, max_length=80)
    size: str | None = None
    nickname: str | None = None
    en_class: str | None = None
    is_own: bool | None = None


class GliderOut(BaseModel):
    id: str
    owner_id: str
    brand: str
    model: str
    size: str | None
    nickname: str | None
    en_class: str | None
    is_own: bool
    retired_at: datetime | None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
