"""Pydantic schemas for sites and per-pilot site preferences."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class SiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    is_launch: bool = False
    is_landing: bool = False
    lat: float | None = None
    lon: float | None = None
    elevation_m: int | None = None
    region_id: str | None = None

    @model_validator(mode="after")
    def _launch_or_landing(self) -> SiteCreate:
        if not self.is_launch and not self.is_landing:
            raise ValueError("A site must be a launch, a landing, or both")
        return self


class SiteUpdate(BaseModel):
    """PATCH semantics — every field optional, applied with exclude_unset=True."""

    name: str | None = Field(None, min_length=1, max_length=120)
    is_launch: bool | None = None
    is_landing: bool | None = None
    lat: float | None = None
    lon: float | None = None
    elevation_m: int | None = None
    region_id: str | None = None


class SiteOut(BaseModel):
    id: str
    owner_id: str | None
    name: str
    is_launch: bool
    is_landing: bool
    lat: float | None
    lon: float | None
    elevation_m: int | None
    elevation_igc_m: int | None
    region_id: str | None
    coord_source: str | None
    coord_accuracy_m: float | None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserSitePrefUpdate(BaseModel):
    """PUT semantics for the caller's own prefs on a site — every field optional."""

    alias: str | None = None
    elevation_m: int | None = None
    is_favourite: bool | None = None
    is_hidden: bool | None = None


class UserSitePrefOut(BaseModel):
    user_id: str
    site_id: str
    alias: str | None
    elevation_m: int | None
    is_favourite: bool
    is_hidden: bool

    model_config = {"from_attributes": True}
