"""
Pydantic response schemas for /api/stats.

No request bodies — every endpoint is a parameterless (or path-param-only) GET. See
specs/005-statistics/data-model.md for the source shapes.
"""

from __future__ import annotations

from pydantic import BaseModel


class TotalsOut(BaseModel):
    total_flights: int
    total_airtime_min: int
    total_distance_km: float
    total_alt_gain_m: int
    avg_airtime_min: float
    avg_airtime_min_excl_training: float
    avg_distance_km: float


class TimeBreakdownOut(BaseModel):
    by_year: dict[int, int]
    by_month: dict[int, int]
    year_month_matrix: dict[int, dict[int, int]]


class DistributionOut(BaseModel):
    duration_buckets: dict[str, int]
    distance_buckets: dict[str, int]
    altitude_buckets: dict[str, int]


class PersonalBestOut(BaseModel):
    label: str
    value: float
    flight_id: str


class DimensionYearMatrixRow(BaseModel):
    name: str | None
    id: str | None
    by_year: dict[int, int]
    total: int


class DimensionYearMatrixOut(BaseModel):
    dimension: str
    rows: list[DimensionYearMatrixRow]


class LaunchTechniqueOut(BaseModel):
    forward: int
    reverse: int
    reverse_pct: float
    hike_fly_total: int


class IgcRollupOut(BaseModel):
    cumulative_thermal_climb_m: float
    tracks_uploaded: int


class CurrentStreakOut(BaseModel):
    unit: str  # "week" | "month"
    count: int


class YtdPaceOut(BaseModel):
    this_year: int
    same_point_prior_year: int


class ProgressionPoint(BaseModel):
    date: str
    cumulative_count: int


class ProgressionOut(BaseModel):
    current_streak: CurrentStreakOut
    ytd_pace: YtdPaceOut
    cumulative_series: list[ProgressionPoint]
