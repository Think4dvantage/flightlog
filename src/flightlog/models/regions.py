"""Pydantic schemas for regions. Read-only — regions are shared reference data, not owner-scoped."""

from __future__ import annotations

from pydantic import BaseModel


class RegionOut(BaseModel):
    id: str
    name: str
    sort_order: int

    model_config = {"from_attributes": True}
