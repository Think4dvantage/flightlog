"""
Flights.

    GET    /api/flights           — filters: year, category_id, glider_id, site_id, region_id
    POST   /api/flights           — import_key is never accepted from the body
    GET    /api/flights/{id}      — includes computed alt_gain_m / site_drop_m / total_descent_m
    PUT    /api/flights/{id}
    DELETE /api/flights/{id}
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user
from flightlog.api.errors import AppException
from flightlog.core.flights import compute_altitude_figures, list_flights
from flightlog.database.db import get_db
from flightlog.database.models import Flight, FlightBuddy, FlightLink, IgcTrack, User
from flightlog.models.flights import FlightCreate, FlightLinkOut, FlightOut, FlightUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/flights", tags=["flights"])


def _get_own_flight(flight_id: str, current_user: User, db: Session) -> Flight:
    """404 whether the row is missing or simply not yours — never a 403."""
    row = db.get(Flight, flight_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Flight not found")
    return row


def _to_out(db: Session, flight: Flight, has_igc_track: bool | None = None) -> FlightOut:
    """
    `has_igc_track` is precomputed and passed in by the caller for a list (see
    `list_flights_route`) — a batched query, not one `IgcTrack` lookup per flight, which
    would be the exact N+1 `04-constraints.md` warns against. Single-flight callers
    (create/get/update) look it up directly here since that's a single row, not a loop.
    `links` follows `buddy_ids`'s existing precedent of one small per-flight query even in
    a list response — flight-links (v0.8) are typically zero or one row per flight.
    """
    buddy_ids = [
        fb.buddy_id for fb in db.query(FlightBuddy).filter(FlightBuddy.flight_id == flight.id)
    ]
    links = db.query(FlightLink).filter(FlightLink.flight_id == flight.id).all()
    out = FlightOut.model_validate(flight, from_attributes=True)
    out.buddy_ids = buddy_ids
    out.links = [FlightLinkOut.model_validate(link) for link in links]
    figures = compute_altitude_figures(db, flight)
    out.alt_gain_m = figures["alt_gain_m"]
    out.site_drop_m = figures["site_drop_m"]
    out.total_descent_m = figures["total_descent_m"]
    if has_igc_track is None:
        has_igc_track = (
            db.query(IgcTrack).filter(IgcTrack.flight_id == flight.id).first() is not None
        )
    out.has_igc_track = has_igc_track
    return out


def _set_buddies(db: Session, flight_id: str, buddy_ids: list[str]) -> None:
    db.query(FlightBuddy).filter(FlightBuddy.flight_id == flight_id).delete()
    for buddy_id in buddy_ids:
        db.add(FlightBuddy(flight_id=flight_id, buddy_id=buddy_id))


@router.get("", response_model=list[FlightOut])
def list_flights_route(
    year: int | None = None,
    category_id: str | None = None,
    glider_id: str | None = None,
    site_id: str | None = None,
    region_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FlightOut]:
    flights = list_flights(
        db,
        current_user.id,
        year=year,
        category_id=category_id,
        glider_id=glider_id,
        site_id=site_id,
        region_id=region_id,
    )
    flight_ids = [f.id for f in flights]
    tracked_ids = (
        {row[0] for row in db.query(IgcTrack.flight_id).filter(IgcTrack.flight_id.in_(flight_ids))}
        if flight_ids
        else set()
    )
    return [_to_out(db, f, has_igc_track=f.id in tracked_ids) for f in flights]


@router.post("", response_model=FlightOut, status_code=201)
def create_flight(
    body: FlightCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FlightOut:
    data = body.model_dump(exclude={"buddy_ids"})
    flight = Flight(owner_id=current_user.id, **data)  # import_key never accepted from body
    db.add(flight)
    db.flush()
    _set_buddies(db, flight.id, body.buddy_ids)
    db.commit()
    db.refresh(flight)
    logger.info("Flight created: %s by %s", flight.id, current_user.id)
    return _to_out(db, flight)


@router.get("/{flight_id}", response_model=FlightOut)
def get_flight(
    flight_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FlightOut:
    flight = _get_own_flight(flight_id, current_user, db)
    return _to_out(db, flight)


@router.put("/{flight_id}", response_model=FlightOut)
def update_flight(
    flight_id: str,
    body: FlightUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FlightOut:
    flight = _get_own_flight(flight_id, current_user, db)
    changes = body.model_dump(exclude_unset=True, exclude={"buddy_ids"})
    for field, value in changes.items():
        setattr(flight, field, value)
    if body.buddy_ids is not None:
        _set_buddies(db, flight.id, body.buddy_ids)
    db.commit()
    db.refresh(flight)
    logger.info("Flight updated: %s by %s", flight.id, current_user.id)
    return _to_out(db, flight)


@router.delete("/{flight_id}", status_code=204)
def delete_flight(
    flight_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    flight = _get_own_flight(flight_id, current_user, db)
    db.delete(flight)
    db.commit()
    logger.info("Flight deleted: %s by %s", flight_id, current_user.id)
