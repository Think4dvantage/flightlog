"""Pydantic schemas for harnesses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HarnessCreate(BaseModel):
    brand: str = Field(..., min_length=1, max_length=80)
    model: str = Field(..., min_length=1, max_length=80)
    size: str | None = None
    harness_type: str | None = None
    reserve_next_repack: datetime | None = None


class HarnessUpdate(BaseModel):
    brand: str | None = Field(None, min_length=1, max_length=80)
    model: str | None = Field(None, min_length=1, max_length=80)
    size: str | None = None
    harness_type: str | None = None
    reserve_next_repack: datetime | None = None


class HarnessOut(BaseModel):
    id: str
    owner_id: str
    brand: str
    model: str
    size: str | None
    harness_type: str | None
    reserve_next_repack: datetime | None
    retired_at: datetime | None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
