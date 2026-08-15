"""Pydantic schemas for hikes, ground-handling sessions, tandem flights, and goals."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class HikeOut(BaseModel):
    id: str
    owner_id: str
    hike_date: date
    start_place: str
    destination_place: str
    ascent_m: int | None
    descent_m: int | None
    distance_km: float | None
    duration_min: int | None
    route_description: str | None
    flight_id: str | None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class GroundhandlingSessionOut(BaseModel):
    id: str
    owner_id: str
    session_date: date
    place: str
    duration_min: int | None
    comment: str | None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TandemFlightOut(BaseModel):
    id: str
    owner_id: str
    flight_date: date
    launch_place: str
    landing_place: str
    tandem_operator: str | None
    comment: str | None
    cost: float | None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class GoalCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    wind_direction: str | None = None
    difficulty: str | None = None
    category: str | None = None
    description: str | None = None
    links: str | None = None
    target_season: str | None = None


class GoalUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    wind_direction: str | None = None
    difficulty: str | None = None
    category: str | None = None
    description: str | None = None
    links: str | None = None
    target_season: str | None = None
    status: str | None = None


class GoalOut(BaseModel):
    id: str
    owner_id: str
    title: str
    wind_direction: str | None
    difficulty: str | None
    category: str | None
    description: str | None
    links: str | None
    target_season: str | None
    status: str
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
