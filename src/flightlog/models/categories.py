"""Pydantic schemas for flight categories."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    is_hike_fly: bool = False
    is_training: bool = False


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    is_hike_fly: bool | None = None
    is_training: bool | None = None


class CategoryOut(BaseModel):
    id: str
    owner_id: str
    name: str
    slug: str
    is_hike_fly: bool
    is_training: bool
    sort_order: int
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class CategoryReorderRequest(BaseModel):
    """Ordered list of category ids — position in the list becomes sort_order."""

    ids: list[str] = Field(..., min_length=1)
