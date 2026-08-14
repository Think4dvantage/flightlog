"""Pydantic schemas for IGC tracks, segments, and bulk-upload review."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class IgcTrackOut(BaseModel):
    id: str
    owner_id: str
    flight_id: str
    original_filename: str
    duration_s: int | None
    distance_km: float | None
    max_alt_igc_m: int | None
    alt_gain_igc_m: int | None
    thermal_count: int | None
    best_climb_ms: float | None
    peak_climb_ms: float | None
    glide_ratio: float | None
    alt_source: str | None
    analyzer_version: str
    analyzed_at: datetime
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class IgcSegmentOut(BaseModel):
    id: str
    kind: str
    start_offset_s: int
    start_at: datetime
    duration_s: int | None
    alt_change_m: float | None
    vertical_velocity_ms: float | None
    glide_ratio: float | None

    model_config = {"from_attributes": True}


class IgcTrackGeometryOut(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]]  # [lon, lat, alt_m] per point


class IgcTrackGeoJsonPropertiesOut(BaseModel):
    offsets_s: list[int]


class IgcTrackGeoJsonOut(BaseModel):
    """A GeoJSON Feature — the LineString geometry carries the map line, `properties.offsets_s`
    (paired with each coordinate's altitude) carries everything the barogram needs, so one
    response serves both without a second endpoint or a raw-file re-parse."""

    type: Literal["Feature"] = "Feature"
    geometry: IgcTrackGeometryOut
    properties: IgcTrackGeoJsonPropertiesOut


class BulkUploadOutcomeOut(BaseModel):
    filename: str
    outcome: Literal["auto_attached", "needs_resolution", "rejected"]
    flight_id: str | None = None
    candidate_flight_ids: list[str] | None = None
    pending_id: str | None = None
    reason: str | None = None


class IgcPendingUploadOut(BaseModel):
    id: str
    original_filename: str
    status: str
    reason: str | None
    candidate_flight_ids: list[str] | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class IgcPendingResolveIn(BaseModel):
    flight_id: str


class ReanalyzeResultOut(BaseModel):
    reanalyzed_count: int
