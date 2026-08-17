"""
The public surface (v0.9) — **unauthenticated by design**.

No `Depends(get_current_user)` or `Depends(get_current_user_optional)` anywhere in this
file, matching health.py's existing "the absence of a dependency is what makes a route
public" precedent (.ai/instructions/02-backend-conventions.md). A request carrying a valid
JWT for some other pilot is never inspected — this surface never uses the caller's own
identity for anything, only the requested id/visibility.

Every route is rate-limited via slowapi, independently of the authenticated surface, keyed
on the same X-Forwarded-For-aware client address dependencies.py's client_ip() already
trusts elsewhere in this app (currently for audit logging only) — not slowapi's default
get_remote_address, which would resolve to the proxy's own IP for every visitor and put
them all in one shared bucket.

Caveat, inherited from client_ip() and not yet independently verified for this new,
higher-stakes use: this assumes the fronting Traefik proxy *replaces* X-Forwarded-For
rather than appending to a client-supplied one. If it appends, a caller could still forge
the leading hop and mint a fresh rate-limit bucket per request. Confirm actual Traefik
behavior before treating this limiter as abuse-resistant, not just accidental-burst-resistant.

A private (or nonexistent) flight and a disabled-or-nonexistent profile return byte-identical
404s — the same AppException call site for both branches, never two independently-written
raises that could drift apart over time.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import client_ip
from flightlog.api.errors import CODE_ENTITY_NOT_FOUND, AppException
from flightlog.config import get_config
from flightlog.core import igc as igc_core
from flightlog.core import stats as stats_core
from flightlog.core.flights import compute_altitude_figures
from flightlog.database.db import get_db
from flightlog.database.models import Flight, FlightCategory, IgcSegment, IgcTrack, Site, User
from flightlog.models.igc import IgcTrackGeometryOut
from flightlog.models.public import (
    PublicFlightOut,
    PublicIgcSegmentOut,
    PublicIgcTrackOut,
    PublicPersonalBestOut,
    PublicProfileFlightOut,
    PublicProfileOut,
    PublicStatsOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["public"])

limiter = Limiter(key_func=client_ip)


def _public_rate_limit() -> str:
    """Resolved per-request, not at decoration time — a bare string would freeze in
    whatever config.yml happened to say at module-import time, before tests (or a config
    reload) can override it."""
    return get_config().api.public_rate_limit


def _not_found(entity: str) -> AppException:
    return AppException(404, CODE_ENTITY_NOT_FOUND, f"{entity} not found")


def _site_name(db: Session, site_id: str | None) -> str | None:
    if site_id is None:
        return None
    site = db.get(Site, site_id)
    return site.name if site is not None else None


def _category_name(db: Session, category_id: str | None) -> str | None:
    if category_id is None:
        return None
    category = db.get(FlightCategory, category_id)
    return category.name if category is not None else None


def _igc_to_public_out(db: Session, flight_id: str) -> PublicIgcTrackOut | None:
    track = db.execute(select(IgcTrack).where(IgcTrack.flight_id == flight_id)).scalar_one_or_none()
    if track is None:
        return None

    segments = (
        db.execute(
            select(IgcSegment)
            .where(IgcSegment.track_id == track.id)
            .order_by(IgcSegment.start_offset_s)
        )
        .scalars()
        .all()
    )
    coordinates, offsets_s = igc_core.parse_simplified_track(track.track_simplified_json)

    return PublicIgcTrackOut(
        duration_s=track.duration_s,
        distance_km=track.distance_km,
        max_alt_igc_m=track.max_alt_igc_m,
        alt_gain_igc_m=track.alt_gain_igc_m,
        thermal_count=track.thermal_count,
        best_climb_ms=track.best_climb_ms,
        peak_climb_ms=track.peak_climb_ms,
        glide_ratio=track.glide_ratio,
        alt_source=track.alt_source,
        geometry=IgcTrackGeometryOut(coordinates=coordinates),
        offsets_s=offsets_s,
        segments=[
            PublicIgcSegmentOut(
                kind=seg.kind, start_offset_s=seg.start_offset_s, duration_s=seg.duration_s
            )
            for seg in segments
        ],
    )


def _stats_to_public_out(db: Session, owner: User) -> PublicStatsOut:
    public_bests = []
    for best in stats_core.personal_bests(db, owner.id):
        flight = db.get(Flight, best.flight_id)
        linkable = flight is not None and flight.visibility in ("unlisted", "public")
        public_bests.append(
            PublicPersonalBestOut(
                label=best.label,
                value=best.value,
                flight_date=best.flight_date,
                flight_id=best.flight_id if linkable else None,
            )
        )

    matrices = {
        dimension: stats_core.year_matrix(db, owner.id, dimension)
        for dimension in stats_core.DIMENSIONS
    }

    return PublicStatsOut(
        owner_id=owner.id,
        owner_display_name=owner.display_name,
        owner_has_public_profile=owner.public_profile_enabled,
        totals=stats_core.totals(db, owner.id),
        time_breakdown=stats_core.time_breakdown(db, owner.id),
        distribution=stats_core.distribution(db, owner.id),
        monthly_extremes=stats_core.monthly_extremes(db, owner.id),
        xc_progression=stats_core.xc_progression(db, owner.id),
        personal_bests=public_bests,
        matrices=matrices,
        launch_technique=stats_core.launch_technique(db, owner.id),
        igc_rollup=stats_core.igc_rollup(db, owner.id),
        progression=stats_core.progression(db, owner.id),
    )


def _flight_to_public_out(db: Session, flight: Flight, owner: User) -> PublicFlightOut:
    figures = compute_altitude_figures(db, flight)

    return PublicFlightOut(
        id=flight.id,
        flight_date=flight.flight_date,
        launch_site_name=_site_name(db, flight.launch_site_id) or "",
        landing_site_name=_site_name(db, flight.landing_site_id),
        category_name=_category_name(db, flight.category_id),
        duration_min=flight.duration_min,
        distance_km=flight.distance_km,
        max_alt_m=flight.max_alt_m,
        alt_gain_m=figures["alt_gain_m"],
        site_drop_m=figures["site_drop_m"],
        total_descent_m=figures["total_descent_m"],
        launch_technique=flight.launch_technique,
        nickname=flight.nickname,
        notes=flight.notes,
        visibility=flight.visibility,
        owner_display_name=owner.display_name,
        owner_id=owner.id,
        owner_has_public_profile=owner.public_profile_enabled,
        igc=_igc_to_public_out(db, flight.id),
    )


@router.get("/flights/{flight_id}", response_model=PublicFlightOut)
@limiter.limit(_public_rate_limit)
def get_public_flight(
    request: Request,  # required by slowapi's decorator, not read directly
    flight_id: str,
    db: Session = Depends(get_db),
) -> PublicFlightOut:
    flight = db.get(Flight, flight_id)
    if flight is None or flight.visibility not in ("unlisted", "public"):
        logger.info("Public flight request rejected: %s", flight_id)
        raise _not_found("Flight")

    owner = db.get(User, flight.owner_id)
    if owner is None:
        raise _not_found("Flight")

    logger.info("Public flight served: %s (visibility=%s)", flight_id, flight.visibility)
    return _flight_to_public_out(db, flight, owner)


@router.get("/stats/{user_id}", response_model=PublicStatsOut)
@limiter.limit(_public_rate_limit)
def get_public_stats(
    request: Request,  # required by slowapi's decorator, not read directly
    user_id: str,
    db: Session = Depends(get_db),
) -> PublicStatsOut:
    owner = db.get(User, user_id)
    if owner is None or not owner.public_stats_enabled:
        logger.info("Public stats request rejected: %s", user_id)
        raise _not_found("Stats")

    logger.info("Public stats served: %s", user_id)
    return _stats_to_public_out(db, owner)


@router.get("/profiles/{user_id}", response_model=PublicProfileOut)
@limiter.limit(_public_rate_limit)
def get_public_profile(
    request: Request,  # required by slowapi's decorator, not read directly
    user_id: str,
    db: Session = Depends(get_db),
) -> PublicProfileOut:
    owner = db.get(User, user_id)
    if owner is None or not owner.public_profile_enabled:
        logger.info("Public profile request rejected: %s", user_id)
        raise _not_found("Profile")

    # public only — an unlisted flight is reachable exclusively by its own direct link,
    # never listed anywhere, including its own owner's public profile (contracts/endpoints.md).
    flights = (
        db.query(Flight)
        .filter(Flight.owner_id == owner.id, Flight.visibility == "public")
        .order_by(Flight.flight_date.desc())
        .all()
    )

    logger.info("Public profile served: %s (%d public flights)", user_id, len(flights))
    return PublicProfileOut(
        user_id=owner.id,
        display_name=owner.display_name,
        public_stats_enabled=owner.public_stats_enabled,
        flights=[
            PublicProfileFlightOut(
                id=f.id,
                flight_date=f.flight_date,
                launch_site_name=_site_name(db, f.launch_site_id) or "",
                category_name=_category_name(db, f.category_id),
                nickname=f.nickname,
                duration_min=f.duration_min,
                distance_km=f.distance_km,
                max_alt_m=f.max_alt_m,
            )
            for f in flights
        ],
    )
