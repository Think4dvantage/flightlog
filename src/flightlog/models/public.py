"""
Pydantic schemas for the unauthenticated public surface (v0.9).

Deliberately NOT inherited from or reusing `FlightOut`/`UserOut` — an explicit field
allowlist so a private field never leaks onto the public surface just because it happened
to exist on the pilot-facing schema. See specs/007-sharing-public-readiness/plan.md's Risk
section.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class PublicFlightOut(BaseModel):
    id: str
    flight_date: date
    launch_site_name: str
    landing_site_name: str | None
    category_name: str | None
    duration_min: int | None
    distance_km: float | None
    max_alt_m: int | None
    alt_gain_m: float | None
    site_drop_m: float | None
    total_descent_m: float | None
    launch_technique: Literal["forward", "reverse"] | None
    nickname: str | None
    notes: str | None
    visibility: Literal["unlisted", "public"]
    owner_display_name: str
    owner_id: str
    owner_has_public_profile: bool


class PublicProfileFlightOut(BaseModel):
    """One row in a public profile's flight list — a smaller allowlist than
    `PublicFlightOut` itself; a profile lists achievements, it doesn't reproduce the full
    single-flight detail view."""

    id: str
    flight_date: date
    launch_site_name: str
    category_name: str | None
    nickname: str | None
    duration_min: int | None
    distance_km: float | None
    max_alt_m: int | None


class PublicProfileOut(BaseModel):
    user_id: str
    display_name: str
    flights: list[PublicProfileFlightOut]
