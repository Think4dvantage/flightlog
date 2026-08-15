"""
Every read-time aggregate query behind /api/stats. No new tables (data-model.md) — every
figure is assembled from `flights` and its already-existing related tables, plus
`igc_tracks`/`igc_segments` for the one IGC-derived rollup.

One batched load per call (`_load_owner_data`) fetches this owner's flights plus every
reference row needed to resolve them, then every other function is pure Python over that
in-memory set. This avoids the N+1 `04-constraints.md` calls out by name ("the N+1 that
kills the flights table and the stats page") — `compute_altitude_figures()` in
`core/flights.py` does a per-flight `db.get()` and is deliberately not reused here.
`launch_technique_split()`/`hike_fly_total()` stay pure functions over a flight list
(06-testing-conventions.md's own pinned example), so a test can duck-type flights with
`SimpleNamespace` and skip the database entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from flightlog.database.models import (
    Buddy,
    Flight,
    FlightBuddy,
    FlightCategory,
    Glider,
    Harness,
    IgcSegment,
    IgcTrack,
    Region,
    Site,
    UserSitePref,
    utcnow,
)
from flightlog.models.stats import (
    CurrentStreakOut,
    DimensionYearMatrixOut,
    DimensionYearMatrixRow,
    DistributionOut,
    IgcRollupOut,
    LaunchTechniqueOut,
    PersonalBestOut,
    ProgressionOut,
    ProgressionPoint,
    TimeBreakdownOut,
    TotalsOut,
    YtdPaceOut,
)

DIMENSIONS = ("site", "region", "glider", "harness", "category", "buddy")

_DIMENSION_FIELD = {
    "site": "launch_site_id",
    "region": "region_id",
    "glider": "glider_id",
    "harness": "harness_id",
    "category": "category_id",
}

_DURATION_BOUNDS = (30, 60, 120, 180)
_DISTANCE_BOUNDS = (10, 25, 50, 100)
_ALTITUDE_BOUNDS = (200, 500, 1000, 2000)


@dataclass
class _EnrichedFlight:
    id: str
    flight_date: date
    duration_min: int | None
    distance_km: float | None
    max_alt_m: int | None
    launch_technique: str | None
    category_id: str
    is_training: bool
    is_hike_fly: bool
    glider_id: str | None
    harness_id: str | None
    launch_site_id: str
    region_id: str | None
    alt_gain_m: float | None
    launch_elev_m: float | None
    landing_elev_m: float | None
    buddy_ids: tuple[str, ...]


@dataclass
class _OwnerData:
    flights: list[_EnrichedFlight]
    sites: dict[str, Site]
    regions: dict[str, Region]
    categories: dict[str, FlightCategory]
    gliders: dict[str, Glider]
    harnesses: dict[str, Harness]
    buddies: dict[str, Buddy]


def _load_owner_data(db: Session, owner_id: str) -> _OwnerData:
    flights = db.execute(select(Flight).where(Flight.owner_id == owner_id)).scalars().all()

    categories = {
        c.id: c
        for c in db.execute(select(FlightCategory).where(FlightCategory.owner_id == owner_id))
        .scalars()
        .all()
    }
    gliders = {
        g.id: g
        for g in db.execute(select(Glider).where(Glider.owner_id == owner_id)).scalars().all()
    }
    harnesses = {
        h.id: h
        for h in db.execute(select(Harness).where(Harness.owner_id == owner_id)).scalars().all()
    }
    buddies = {
        b.id: b for b in db.execute(select(Buddy).where(Buddy.owner_id == owner_id)).scalars().all()
    }
    regions = {r.id: r for r in db.execute(select(Region)).scalars().all()}

    site_ids = {f.launch_site_id for f in flights} | {
        f.landing_site_id for f in flights if f.landing_site_id
    }
    sites: dict[str, Site] = {}
    prefs: dict[str, UserSitePref] = {}
    if site_ids:
        sites = {
            s.id: s for s in db.execute(select(Site).where(Site.id.in_(site_ids))).scalars().all()
        }
        prefs = {
            p.site_id: p
            for p in db.execute(
                select(UserSitePref).where(
                    UserSitePref.user_id == owner_id, UserSitePref.site_id.in_(site_ids)
                )
            )
            .scalars()
            .all()
        }

    buddy_links: dict[str, list[str]] = {}
    flight_ids = [f.id for f in flights]
    if flight_ids:
        for row in (
            db.execute(select(FlightBuddy).where(FlightBuddy.flight_id.in_(flight_ids)))
            .scalars()
            .all()
        ):
            buddy_links.setdefault(row.flight_id, []).append(row.buddy_id)

    def elev(site_id: str | None, override: int | None) -> float | None:
        """COALESCE(flight override, user_site_prefs override, sites.elevation_m)."""
        if override is not None:
            return override
        if site_id is None:
            return None
        pref = prefs.get(site_id)
        if pref is not None and pref.elevation_m is not None:
            return pref.elevation_m
        site = sites.get(site_id)
        return site.elevation_m if site else None

    enriched: list[_EnrichedFlight] = []
    for f in flights:
        category = categories.get(f.category_id)
        launch_site = sites.get(f.launch_site_id)
        launch_elev_m = elev(f.launch_site_id, f.launch_elev_override_m)
        landing_elev_m = elev(f.landing_site_id, f.landing_elev_override_m)
        alt_gain_m = (
            f.max_alt_m - launch_elev_m
            if f.max_alt_m is not None and launch_elev_m is not None
            else None
        )
        enriched.append(
            _EnrichedFlight(
                id=f.id,
                flight_date=f.flight_date,
                duration_min=f.duration_min,
                distance_km=f.distance_km,
                max_alt_m=f.max_alt_m,
                launch_technique=f.launch_technique,
                category_id=f.category_id,
                is_training=bool(category.is_training) if category else False,
                is_hike_fly=bool(category.is_hike_fly) if category else False,
                glider_id=f.glider_id,
                harness_id=f.harness_id,
                launch_site_id=f.launch_site_id,
                region_id=launch_site.region_id if launch_site else None,
                alt_gain_m=alt_gain_m,
                launch_elev_m=launch_elev_m,
                landing_elev_m=landing_elev_m,
                buddy_ids=tuple(buddy_links.get(f.id, [])),
            )
        )

    return _OwnerData(
        flights=enriched,
        sites=sites,
        regions=regions,
        categories=categories,
        gliders=gliders,
        harnesses=harnesses,
        buddies=buddies,
    )


# ---- P1: totals, time breakdown, distribution, personal bests ----


def totals(db: Session, owner_id: str) -> TotalsOut:
    flights = _load_owner_data(db, owner_id).flights

    durations = [f.duration_min for f in flights if f.duration_min is not None]
    durations_excl_training = [
        f.duration_min for f in flights if f.duration_min is not None and not f.is_training
    ]
    distances = [f.distance_km for f in flights if f.distance_km is not None]

    return TotalsOut(
        total_flights=len(flights),
        total_airtime_min=sum(durations),
        total_distance_km=sum(distances),
        total_alt_gain_m=round(sum(f.alt_gain_m or 0 for f in flights)),
        avg_airtime_min=(sum(durations) / len(durations)) if durations else 0.0,
        avg_airtime_min_excl_training=(
            (sum(durations_excl_training) / len(durations_excl_training))
            if durations_excl_training
            else 0.0
        ),
        avg_distance_km=(sum(distances) / len(distances)) if distances else 0.0,
    )


def time_breakdown(db: Session, owner_id: str) -> TimeBreakdownOut:
    flights = _load_owner_data(db, owner_id).flights

    by_year: dict[int, int] = {}
    by_month: dict[int, int] = {}
    matrix: dict[int, dict[int, int]] = {}
    for f in flights:
        year, month = f.flight_date.year, f.flight_date.month
        by_year[year] = by_year.get(year, 0) + 1
        by_month[month] = by_month.get(month, 0) + 1
        year_bucket = matrix.setdefault(year, {})
        year_bucket[month] = year_bucket.get(month, 0) + 1

    return TimeBreakdownOut(by_year=by_year, by_month=by_month, year_month_matrix=matrix)


def _bucket_labels(bounds: tuple[int, ...], unit: str) -> list[str]:
    labels = [f"<{bounds[0]}{unit}"]
    labels += [f"{bounds[i]}-{bounds[i + 1]}{unit}" for i in range(len(bounds) - 1)]
    labels.append(f">{bounds[-1]}{unit}")
    return labels


def _bucket_for(value: float | None, bounds: tuple[int, ...], labels: list[str]) -> str | None:
    if value is None:
        return None
    for bound, label in zip(bounds, labels, strict=False):
        if value < bound:
            return label
    return labels[-1]


def distribution(db: Session, owner_id: str) -> DistributionOut:
    flights = _load_owner_data(db, owner_id).flights

    duration_labels = _bucket_labels(_DURATION_BOUNDS, "min")
    distance_labels = _bucket_labels(_DISTANCE_BOUNDS, "km")
    altitude_labels = _bucket_labels(_ALTITUDE_BOUNDS, "m")

    duration_buckets = dict.fromkeys(duration_labels, 0)
    distance_buckets = dict.fromkeys(distance_labels, 0)
    altitude_buckets = dict.fromkeys(altitude_labels, 0)

    for f in flights:
        label = _bucket_for(f.duration_min, _DURATION_BOUNDS, duration_labels)
        if label:
            duration_buckets[label] += 1
        label = _bucket_for(f.distance_km, _DISTANCE_BOUNDS, distance_labels)
        if label:
            distance_buckets[label] += 1
        label = _bucket_for(f.alt_gain_m, _ALTITUDE_BOUNDS, altitude_labels)
        if label:
            altitude_buckets[label] += 1

    return DistributionOut(
        duration_buckets=duration_buckets,
        distance_buckets=distance_buckets,
        altitude_buckets=altitude_buckets,
    )


# label -> (attribute getter, is_min)
_PERSONAL_BEST_SPECS: tuple[tuple[str, str, bool], ...] = (
    ("longest_airtime", "duration_min", False),
    ("max_altitude", "max_alt_m", False),
    ("highest_launch", "launch_elev_m", False),
    ("lowest_launch", "launch_elev_m", True),
    ("highest_landing", "landing_elev_m", False),
    ("lowest_landing", "landing_elev_m", True),
    ("longest_distance", "distance_km", False),
    ("shortest_distance", "distance_km", True),
)


def personal_bests(db: Session, owner_id: str) -> list[PersonalBestOut]:
    flights = _load_owner_data(db, owner_id).flights

    results: list[PersonalBestOut] = []
    for label, attr, is_min in _PERSONAL_BEST_SPECS:
        candidates = [(getattr(f, attr), f) for f in flights if getattr(f, attr) is not None]
        if not candidates:
            continue
        best_value = min(v for v, _ in candidates) if is_min else max(v for v, _ in candidates)
        tied = [f for v, f in candidates if v == best_value]
        # Deterministic across page loads: earliest flight_date, then id.
        winner = min(tied, key=lambda f: (f.flight_date, f.id))
        results.append(PersonalBestOut(label=label, value=best_value, flight_id=winner.id))

    return results


# ---- P1 continued: dimension matrices, launch technique ----


def _name_for(dimension: str, dim_id: str | None, owner_data: _OwnerData) -> str | None:
    if dim_id is None:
        return None
    if dimension == "site":
        site = owner_data.sites.get(dim_id)
        return site.name if site else None
    if dimension == "region":
        region = owner_data.regions.get(dim_id)
        return region.name if region else None
    if dimension == "glider":
        glider = owner_data.gliders.get(dim_id)
        if glider is None:
            return None
        return glider.nickname or " ".join(filter(None, [glider.brand, glider.model, glider.size]))
    if dimension == "harness":
        harness = owner_data.harnesses.get(dim_id)
        if harness is None:
            return None
        return " ".join(filter(None, [harness.brand, harness.model, harness.size]))
    if dimension == "category":
        category = owner_data.categories.get(dim_id)
        return category.name if category else None
    if dimension == "buddy":
        buddy = owner_data.buddies.get(dim_id)
        return buddy.display_name if buddy else None
    return None


def _rows_from_entries(entries: list[tuple[int, str | None]], owner_data, dimension: str):
    groups: dict[str | None, dict] = {}
    for year, dim_id in entries:
        group = groups.setdefault(
            dim_id,
            {
                "name": _name_for(dimension, dim_id, owner_data),
                "id": dim_id,
                "by_year": {},
                "total": 0,
            },
        )
        group["by_year"][year] = group["by_year"].get(year, 0) + 1
        group["total"] += 1

    rows = [DimensionYearMatrixRow(**g) for g in groups.values()]
    rows.sort(key=lambda r: (-r.total, r.name or ""))
    return rows


def year_matrix(db: Session, owner_id: str, dimension: str) -> DimensionYearMatrixOut:
    """
    Shared "dimension x year" shape for every matrix (`research.md`'s decision) — site,
    region, glider, harness, category share one direct-FK code path; buddy is handled
    separately since it comes through the `flight_buddies` join table and can contribute
    more than one row per flight.
    """
    owner_data = _load_owner_data(db, owner_id)

    if dimension == "buddy":
        entries = [
            (f.flight_date.year, buddy_id) for f in owner_data.flights for buddy_id in f.buddy_ids
        ]
        return DimensionYearMatrixOut(
            dimension="buddy", rows=_rows_from_entries(entries, owner_data, "buddy")
        )

    field = _DIMENSION_FIELD[dimension]
    entries = [(f.flight_date.year, getattr(f, field)) for f in owner_data.flights]
    return DimensionYearMatrixOut(
        dimension=dimension, rows=_rows_from_entries(entries, owner_data, dimension)
    )


def launch_technique_split(flights) -> dict:
    """
    Pure function over a flight-like list (06-testing-conventions.md's own pinned
    example — duck-typed, DB-free). `reverse_pct` is computed over every flight, never a
    stale sub-range: the workbook's own 33.5% is a confirmed formula bug over a truncated
    range (`architecture.md`), and this must disagree with it, not match it.
    """
    total = len(flights)
    forward = sum(1 for f in flights if f.launch_technique == "forward")
    reverse = sum(1 for f in flights if f.launch_technique == "reverse")
    reverse_pct = (reverse / total * 100) if total else 0.0
    return {"forward": forward, "reverse": reverse, "reverse_pct": reverse_pct}


def hike_fly_total(flights) -> int:
    return sum(1 for f in flights if f.is_hike_fly)


def launch_technique(db: Session, owner_id: str) -> LaunchTechniqueOut:
    flights = _load_owner_data(db, owner_id).flights
    split = launch_technique_split(flights)
    return LaunchTechniqueOut(
        forward=split["forward"],
        reverse=split["reverse"],
        reverse_pct=split["reverse_pct"],
        hike_fly_total=hike_fly_total(flights),
    )


# ---- P2: IGC rollup, streaks/pace/progression ----


def igc_rollup(db: Session, owner_id: str) -> IgcRollupOut:
    """
    SUM(igc_segments.alt_change_m) WHERE kind = 'thermal', joined across the owner's
    tracks — a genuine cross-table SQL aggregate rather than a Python loop, since
    `igc_segments` isn't otherwise loaded for any other figure on this page
    (`research.md` — no extra filtering needed, every stored thermal segment is already
    guaranteed climbing).
    """
    total = db.execute(
        select(func.sum(IgcSegment.alt_change_m))
        .select_from(IgcSegment)
        .join(IgcTrack, IgcSegment.track_id == IgcTrack.id)
        .where(IgcTrack.owner_id == owner_id, IgcSegment.kind == "thermal")
    ).scalar()
    tracks_uploaded = db.execute(
        select(func.count(IgcTrack.id)).where(IgcTrack.owner_id == owner_id)
    ).scalar()

    return IgcRollupOut(
        cumulative_thermal_climb_m=total or 0.0,
        tracks_uploaded=tracks_uploaded or 0,
    )


def _iso_week(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return (iso[0], iso[1])


def _week_before(iso_year: int, iso_week: int) -> tuple[int, int]:
    monday = date.fromisocalendar(iso_year, iso_week, 1) - timedelta(days=7)
    return _iso_week(monday)


def current_streak(flights, today: date) -> dict:
    """
    Consecutive ISO weeks with >=1 flight, ending at the most recent flight — broken
    (count 0) once the most recent flight is more than one week stale relative to `today`.
    """
    if not flights:
        return {"unit": "week", "count": 0}

    weeks_with_flight = {_iso_week(f.flight_date) for f in flights}
    current_iso = _iso_week(today)
    previous_iso = _week_before(*current_iso)

    latest_active = max(weeks_with_flight)
    if latest_active not in (current_iso, previous_iso):
        return {"unit": "week", "count": 0}

    count = 0
    cursor = latest_active
    while cursor in weeks_with_flight:
        count += 1
        cursor = _week_before(*cursor)

    return {"unit": "week", "count": count}


def ytd_pace(flights, today: date) -> dict:
    """Flight count from Jan 1 to today's month/day, this year vs. the same window last year."""
    this_year_count = sum(
        1 for f in flights if f.flight_date.year == today.year and f.flight_date <= today
    )

    prior_year = today.year - 1
    try:
        prior_cutoff = today.replace(year=prior_year)
    except ValueError:
        # today is Feb 29 and prior_year isn't a leap year.
        prior_cutoff = date(prior_year, 2, 28)

    prior_count = sum(
        1 for f in flights if f.flight_date.year == prior_year and f.flight_date <= prior_cutoff
    )

    return {"this_year": this_year_count, "same_point_prior_year": prior_count}


def cumulative_progression(flights) -> list[dict]:
    ordered = sorted(flights, key=lambda f: (f.flight_date, f.id))
    return [
        {"date": f.flight_date.isoformat(), "cumulative_count": count}
        for count, f in enumerate(ordered, start=1)
    ]


def progression(db: Session, owner_id: str, today: date | None = None) -> ProgressionOut:
    if today is None:
        today = utcnow().date()

    flights = _load_owner_data(db, owner_id).flights
    streak = current_streak(flights, today)
    pace = ytd_pace(flights, today)
    series = cumulative_progression(flights)

    return ProgressionOut(
        current_streak=CurrentStreakOut(**streak),
        ytd_pace=YtdPaceOut(**pace),
        cumulative_series=[ProgressionPoint(**p) for p in series],
    )
