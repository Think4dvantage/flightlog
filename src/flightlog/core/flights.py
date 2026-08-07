"""
Flight listing, filtering and the derived altitude figures.

alt_gain_m / site_drop_m / total_descent_m are computed here, never stored — see
.ai/context/architecture.md for why (a site elevation correction must retroactively fix every
flight). "Effective" elevation is COALESCE(flight override, user_site_prefs override,
sites.elevation_m).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.database.models import Flight, Site, UserSitePref


def list_flights(
    db: Session,
    owner_id: str,
    year: int | None = None,
    category_id: str | None = None,
    glider_id: str | None = None,
    site_id: str | None = None,
    region_id: str | None = None,
) -> list[Flight]:
    stmt = select(Flight).where(Flight.owner_id == owner_id)

    if year is not None:
        stmt = stmt.where(
            Flight.flight_date >= f"{year}-01-01", Flight.flight_date <= f"{year}-12-31"
        )
    if category_id is not None:
        stmt = stmt.where(Flight.category_id == category_id)
    if glider_id is not None:
        stmt = stmt.where(Flight.glider_id == glider_id)
    if site_id is not None:
        stmt = stmt.where((Flight.launch_site_id == site_id) | (Flight.landing_site_id == site_id))
    if region_id is not None:
        region_site_ids = select(Site.id).where(Site.region_id == region_id)
        stmt = stmt.where(
            Flight.launch_site_id.in_(region_site_ids) | Flight.landing_site_id.in_(region_site_ids)
        )

    return db.execute(stmt.order_by(Flight.flight_date.desc())).scalars().all()


def effective_elevation_m(
    db: Session, owner_id: str, site_id: str | None, flight_override_m: int | None
) -> float | None:
    """COALESCE(flight override, user_site_prefs override, sites.elevation_m)."""
    if flight_override_m is not None:
        return flight_override_m
    if site_id is None:
        return None

    pref = db.get(UserSitePref, (owner_id, site_id))
    if pref is not None and pref.elevation_m is not None:
        return pref.elevation_m

    site = db.get(Site, site_id)
    return site.elevation_m if site is not None else None


def compute_altitude_figures(db: Session, flight: Flight) -> dict[str, float | None]:
    """Returns alt_gain_m, site_drop_m, total_descent_m for one flight — never persisted."""
    launch_elev = effective_elevation_m(
        db, flight.owner_id, flight.launch_site_id, flight.launch_elev_override_m
    )
    landing_elev = effective_elevation_m(
        db, flight.owner_id, flight.landing_site_id, flight.landing_elev_override_m
    )

    alt_gain_m = None
    if flight.max_alt_m is not None and launch_elev is not None:
        alt_gain_m = flight.max_alt_m - launch_elev

    site_drop_m = None
    if launch_elev is not None and landing_elev is not None:
        site_drop_m = launch_elev - landing_elev

    total_descent_m = None
    if flight.max_alt_m is not None and landing_elev is not None:
        total_descent_m = flight.max_alt_m - landing_elev

    return {
        "alt_gain_m": alt_gain_m,
        "site_drop_m": site_drop_m,
        "total_descent_m": total_descent_m,
    }
