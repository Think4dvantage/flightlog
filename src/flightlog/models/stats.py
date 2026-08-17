"""
Pydantic response schemas for /api/stats.

No request bodies — every endpoint is a parameterless (or path-param-only) GET. See
specs/005-statistics/data-model.md for the source shapes.
"""

from __future__ import annotations

from datetime import date

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


class MonthlyExtremesOut(BaseModel):
    """The single best (max) duration/distance/alt_gain per calendar month, across all years —
    "in what month did I get my longest/farthest/highest flight," not an average. All 12 months
    are always present; a month with no flights is `null`, not `0` (a flight of zero minutes
    would be a nonsensical record, not "no data")."""

    max_duration_min_by_month: dict[int, float | None]
    max_distance_km_by_month: dict[int, float | None]
    max_alt_gain_m_by_month: dict[int, float | None]


class PersonalBestOut(BaseModel):
    label: str
    value: float
    flight_id: str
    flight_date: date


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
    total_thermals: int
    total_igc_airtime_min: float
    avg_thermals_by_month: dict[int, float | None]


class CurrentStreakOut(BaseModel):
    unit: str  # "week" | "month"
    count: int


class YtdPaceOut(BaseModel):
    this_year: int
    same_point_prior_year: int


class ProgressionOut(BaseModel):
    """
    No `cumulative_series` field — a running total by date is monotonically increasing by
    construction and was found to carry no information (a straight line bottom-left to
    top-right regardless of the pilot's real activity pattern). Replaced entirely by the
    frontend's "monthly flights per year, overlaid" chart, built client-side from
    `TimeBreakdownOut.year_month_matrix` (no new backend data needed).
    """

    current_streak: CurrentStreakOut
    ytd_pace: YtdPaceOut
    days_since_last_flight: int | None
    last_flight_date: date | None


class XcProgressionYearRow(BaseModel):
    year: int
    total_flights: int
    xc_shaped_flights: int
    xc_pct: float


class XcProgressionOut(BaseModel):
    """
    Per-year share of flights that are "XC-shaped" — distance_km at or above
    `threshold_km` — as a category-name-independent proxy for "real" cross-country flying
    vs. short local hops. Never keys off a flight_categories.name string (free text, not a
    stable enum); `threshold_km` reuses distribution()'s own first distance bucket
    boundary (10km) rather than inventing a second number.
    """

    threshold_km: float
    rows: list[XcProgressionYearRow]
