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

from flightlog.models.igc import IgcTrackGeometryOut
from flightlog.models.stats import (
    DimensionYearMatrixOut,
    DistributionOut,
    IgcRollupOut,
    LaunchTechniqueOut,
    MonthlyExtremesOut,
    ProgressionOut,
    TimeBreakdownOut,
    TotalsOut,
    XcProgressionOut,
)


class PublicIgcSegmentOut(BaseModel):
    """Only the three fields the public barogram's shading actually reads — `alt_change_m`/
    `vertical_velocity_ms`/`glide_ratio`/`start_at`/`id` from the private `IgcSegmentOut` are
    dropped, same explicit-allowlist rule as everything else in this module."""

    kind: str
    start_offset_s: int
    duration_s: int | None


class PublicIgcTrackOut(BaseModel):
    duration_s: int | None
    distance_km: float | None
    max_alt_igc_m: int | None
    alt_gain_igc_m: int | None
    thermal_count: int | None
    best_climb_ms: float | None
    peak_climb_ms: float | None
    glide_ratio: float | None
    alt_source: str | None
    geometry: IgcTrackGeometryOut
    offsets_s: list[int]
    segments: list[PublicIgcSegmentOut]


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
    igc: PublicIgcTrackOut | None = None


class PublicPersonalBestOut(BaseModel):
    """`flight_id` is only set when that specific flight is itself public/unlisted —
    `personal_bests()` draws from the pilot's entire flight history, so a record's own flight
    can be private even though the aggregate number itself is shown (v0.9.5 scope decision,
    confirmed with the pilot: public stats mirror the authenticated page's full lifetime
    numbers). Never link to a flight a visitor can't actually reach."""

    label: str
    value: float
    flight_date: date
    flight_id: str | None


class PublicStatsOut(BaseModel):
    """Reuses `models/stats.py`'s response shapes directly for every sub-object except
    personal bests — unlike `FlightOut`/`UserOut`, none of those carry (or could plausibly
    grow) an owner-identifying or credential field, so the "never inherit the private schema"
    rule's underlying purpose doesn't apply to them. Confirmed with the pilot: public stats
    mirror the authenticated /stats page's entire lifetime history, buddy names included —
    not scoped down to public-visibility flights only."""

    owner_id: str
    owner_display_name: str
    owner_has_public_profile: bool
    totals: TotalsOut
    time_breakdown: TimeBreakdownOut
    distribution: DistributionOut
    monthly_extremes: MonthlyExtremesOut
    xc_progression: XcProgressionOut
    personal_bests: list[PublicPersonalBestOut]
    matrices: dict[str, DimensionYearMatrixOut]
    launch_technique: LaunchTechniqueOut
    igc_rollup: IgcRollupOut
    progression: ProgressionOut


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
    public_stats_enabled: bool
