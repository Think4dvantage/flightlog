"""
Pydantic schemas for `/api/integration/v1` (v0.8) — the API-key-authenticated surface an
external tool like VidFactory reads. Frozen contract: a breaking change to any of these
shapes is a new version, never a silent edit (spec.md's Success Criteria).

Unlike the pilot-facing `FlightOut` (which returns bare ids and lets the browser's own
refdata cache resolve names), `FlightMetadataOut` resolves site/gear/category **names**
server-side — an external tool has no other way to look those up.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class IgcSummaryOut(BaseModel):
    """The track-level aggregates already shown to the pilot via `GET /api/flights/{id}/igc`
    — present only when the flight has an analyzed track."""

    duration_s: int | None
    distance_km: float | None
    max_alt_igc_m: int | None
    alt_gain_igc_m: int | None
    thermal_count: int | None
    best_climb_ms: float | None
    peak_climb_ms: float | None
    glide_ratio: float | None

    model_config = {"from_attributes": True}


class FlightLinkOut(BaseModel):
    kind: str
    external_id: str
    url: str
    label: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class FlightMetadataOut(BaseModel):
    id: str
    flight_date: date
    takeoff_time: datetime | None
    landing_time: datetime | None
    launch_site_name: str | None
    landing_site_name: str | None
    category_name: str | None
    glider_name: str | None
    harness_name: str | None
    launch_technique: Literal["forward", "reverse"] | None
    duration_min: int | None
    distance_km: float | None
    max_alt_m: int | None
    alt_gain_m: float | None
    site_drop_m: float | None
    total_descent_m: float | None
    has_igc_track: bool
    igc_summary: IgcSummaryOut | None = None
    links: list[FlightLinkOut] = Field(default_factory=list)


class SegmentOut(BaseModel):
    """Verbatim `igc_segments` shape — `kind` in thermal|glide|takeoff|landing|max_alt|
    top_of_climb. `start_offset_s` (seconds since takeoff) is the load-bearing field for a
    video timeline; never a video-relative offset, which this service has no way to know."""

    kind: str
    start_offset_s: int
    start_at: datetime
    duration_s: int | None
    alt_change_m: float | None
    vertical_velocity_ms: float | None
    glide_ratio: float | None

    model_config = {"from_attributes": True}


class FlightLinkIn(BaseModel):
    url: str
    label: str | None = Field(None, max_length=200)

    @field_validator("url")
    @classmethod
    def _validate_scheme(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v
