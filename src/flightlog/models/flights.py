"""
Pydantic schemas for flights.

`import_key` and `owner_id` are never accepted from the client — the former is server-generated
(NULL for API-created flights, "xlsx:<row>" only from the importer), the latter always comes from
`current_user.id`. Neither appears in `FlightCreate`/`FlightUpdate`.

`alt_gain_m` / `site_drop_m` / `total_descent_m` on `FlightOut` are **not** ORM attributes — they
are computed by the router at serialization time from `max_alt_m` and the effective launch/landing
elevations. See `.ai/context/architecture.md`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class FlightCreate(BaseModel):
    flight_date: date
    launch_site_id: str
    landing_site_id: str | None = None
    category_id: str
    glider_id: str | None = None
    harness_id: str | None = None
    duration_min: int | None = Field(None, ge=0)
    distance_km: float | None = Field(None, ge=0)
    max_alt_m: int | None = None
    launch_elev_override_m: int | None = None
    landing_elev_override_m: int | None = None
    launch_technique: Literal["forward", "reverse"] | None = None
    notes: str | None = Field(None, max_length=3300)
    buddy_ids: list[str] = Field(default_factory=list)


class FlightUpdate(BaseModel):
    """PATCH semantics — every field optional, applied with exclude_unset=True."""

    flight_date: date | None = None
    launch_site_id: str | None = None
    landing_site_id: str | None = None
    category_id: str | None = None
    glider_id: str | None = None
    harness_id: str | None = None
    duration_min: int | None = Field(None, ge=0)
    distance_km: float | None = Field(None, ge=0)
    max_alt_m: int | None = None
    launch_elev_override_m: int | None = None
    landing_elev_override_m: int | None = None
    launch_technique: Literal["forward", "reverse"] | None = None
    notes: str | None = Field(None, max_length=3300)
    buddy_ids: list[str] | None = None


class FlightLinkOut(BaseModel):
    """
    The pilot-facing view of a `flight_links` row (v0.8) — deliberately a separate type
    from `models.integration.FlightLinkOut`. That one is part of the frozen
    `/api/integration/v1` contract; this one is free to change with the rest of `FlightOut`.
    Coupling the two would mean an integration-surface version bump silently changing the
    pilot-facing `/api/flights` response, or vice versa.
    """

    kind: str
    external_id: str
    url: str
    label: str | None

    model_config = {"from_attributes": True}


class FlightOut(BaseModel):
    id: str
    owner_id: str
    flight_date: date
    takeoff_time: datetime | None
    landing_time: datetime | None
    launch_site_id: str
    landing_site_id: str | None
    category_id: str
    glider_id: str | None
    harness_id: str | None
    duration_min: int | None
    distance_km: float | None
    max_alt_m: int | None
    launch_elev_override_m: int | None
    landing_elev_override_m: int | None
    launch_technique: Literal["forward", "reverse"] | None
    notes: str | None
    import_key: str | None
    buddy_ids: list[str] = Field(default_factory=list)
    alt_gain_m: float | None = None
    site_drop_m: float | None = None
    total_descent_m: float | None = None
    has_igc_track: bool = False
    links: list[FlightLinkOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
