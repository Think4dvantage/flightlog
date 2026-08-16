"""
`/api/integration/v1` — API-key-authenticated (`X-API-Key` header), for an external tool
like VidFactory. Never confuse with `api/routers/api_keys.py`, which is JWT-authenticated
and serves the pilot's own browser session.

    GET /api/integration/v1/flights/{id}                          — flights:read
    GET /api/integration/v1/flights/{id}/segments                 — flights:read
    PUT /api/integration/v1/flights/{id}/links/{kind}/{external_id} — flight_links:write

Every route scopes its query by the key's *owning pilot* (`principal.user.id`), never a
JWT-authenticated `current_user` — there is no JWT-authenticated user in this request at
all. A flight that doesn't exist or isn't owned by this key's pilot is 404, matching this
app's existing "never leak existence" rule — never a 403 that would confirm it exists under
someone else's account.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import ApiPrincipal, require_scope
from flightlog.api.errors import CODE_ENTITY_NOT_FOUND, AppException
from flightlog.core.flights import compute_altitude_figures
from flightlog.database.db import get_db
from flightlog.database.models import (
    Flight,
    FlightCategory,
    FlightLink,
    Glider,
    Harness,
    IgcSegment,
    IgcTrack,
    Site,
)
from flightlog.models.integration import (
    FlightLinkIn,
    FlightLinkOut,
    FlightMetadataOut,
    IgcSummaryOut,
    SegmentOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integration/v1", tags=["integration"])


def _get_own_flight(flight_id: str, principal: ApiPrincipal, db: Session) -> Flight:
    row = db.get(Flight, flight_id)
    if row is None or row.owner_id != principal.user.id:
        raise AppException(404, CODE_ENTITY_NOT_FOUND, "Flight not found")
    return row


def _glider_name(glider: Glider | None) -> str | None:
    if glider is None:
        return None
    return glider.nickname or " ".join(filter(None, [glider.brand, glider.model, glider.size]))


def _harness_name(harness: Harness | None) -> str | None:
    if harness is None:
        return None
    return " ".join(filter(None, [harness.brand, harness.model, harness.size]))


def _to_metadata_out(db: Session, flight: Flight) -> FlightMetadataOut:
    launch_site = db.get(Site, flight.launch_site_id) if flight.launch_site_id else None
    landing_site = db.get(Site, flight.landing_site_id) if flight.landing_site_id else None
    category = db.get(FlightCategory, flight.category_id) if flight.category_id else None
    glider = db.get(Glider, flight.glider_id) if flight.glider_id else None
    harness = db.get(Harness, flight.harness_id) if flight.harness_id else None
    track = db.execute(select(IgcTrack).where(IgcTrack.flight_id == flight.id)).scalar_one_or_none()
    links = db.execute(select(FlightLink).where(FlightLink.flight_id == flight.id)).scalars().all()
    figures = compute_altitude_figures(db, flight)

    return FlightMetadataOut(
        id=flight.id,
        flight_date=flight.flight_date,
        takeoff_time=flight.takeoff_time,
        landing_time=flight.landing_time,
        launch_site_name=launch_site.name if launch_site else None,
        landing_site_name=landing_site.name if landing_site else None,
        category_name=category.name if category else None,
        glider_name=_glider_name(glider),
        harness_name=_harness_name(harness),
        launch_technique=flight.launch_technique,
        duration_min=flight.duration_min,
        distance_km=flight.distance_km,
        max_alt_m=flight.max_alt_m,
        alt_gain_m=figures["alt_gain_m"],
        site_drop_m=figures["site_drop_m"],
        total_descent_m=figures["total_descent_m"],
        has_igc_track=track is not None,
        igc_summary=IgcSummaryOut.model_validate(track) if track else None,
        links=[FlightLinkOut.model_validate(link) for link in links],
    )


@router.get("/flights/{flight_id}", response_model=FlightMetadataOut)
def get_flight_metadata(
    flight_id: str,
    principal: ApiPrincipal = Depends(require_scope("flights:read")),
    db: Session = Depends(get_db),
) -> FlightMetadataOut:
    flight = _get_own_flight(flight_id, principal, db)
    return _to_metadata_out(db, flight)


@router.get("/flights/{flight_id}/segments", response_model=list[SegmentOut])
def get_flight_segments(
    flight_id: str,
    principal: ApiPrincipal = Depends(require_scope("flights:read")),
    db: Session = Depends(get_db),
) -> list[SegmentOut]:
    flight = _get_own_flight(flight_id, principal, db)
    track = db.execute(select(IgcTrack).where(IgcTrack.flight_id == flight.id)).scalar_one_or_none()
    if track is None:
        raise AppException(404, CODE_ENTITY_NOT_FOUND, "No IGC track for this flight")
    rows = (
        db.execute(
            select(IgcSegment)
            .where(IgcSegment.track_id == track.id)
            .order_by(IgcSegment.start_offset_s)
        )
        .scalars()
        .all()
    )
    return [SegmentOut.model_validate(row) for row in rows]


@router.put("/flights/{flight_id}/links/{kind}/{external_id}", response_model=FlightLinkOut)
def put_flight_link(
    flight_id: str,
    kind: str,
    external_id: str,
    body: FlightLinkIn,
    principal: ApiPrincipal = Depends(require_scope("flight_links:write")),
    db: Session = Depends(get_db),
) -> FlightLinkOut:
    """Idempotent create-or-replace on (flight_id, kind, external_id) — a re-push (e.g. a
    re-rendered video) updates the existing link rather than accumulating a duplicate."""
    flight = _get_own_flight(flight_id, principal, db)
    row = db.execute(
        select(FlightLink).where(
            FlightLink.flight_id == flight.id,
            FlightLink.kind == kind,
            FlightLink.external_id == external_id,
        )
    ).scalar_one_or_none()

    created = row is None
    if row is None:
        row = FlightLink(flight_id=flight.id, kind=kind, external_id=external_id)
        db.add(row)
    row.url = body.url
    row.label = body.label
    db.commit()
    db.refresh(row)
    logger.info(
        "Flight link %s: %s/%s on flight %s by key %s",
        "created" if created else "replaced",
        kind,
        external_id,
        flight.id,
        principal.key.id,
    )

    return FlightLinkOut.model_validate(row)
