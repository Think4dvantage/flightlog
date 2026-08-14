"""
Fills in a site's map coordinates from real GPS data once enough tracks have flown there —
never geocoded, only ever a median of track fixes, and never overwriting a coordinate the
pilot placed by hand (architecture.md's "Coordinates are backfilled, never geocoded").
"""

from __future__ import annotations

import logging
import statistics

from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.database.models import Flight, IgcTrack, Site, SiteObservation

logger = logging.getLogger(__name__)

# At least this many independent fixes before trusting a median over a single cold-start
# GPS outlier (architecture.md).
MIN_OBSERVATIONS = 3


def record_observations(db: Session, track: IgcTrack, flight: Flight, analysis) -> None:
    """Insert this track's takeoff/landing site_observations. Call after deleting any prior
    observations for this track (replace path, FR-004) — never accumulates duplicates for
    the same track. `analysis` is a core.igc.AnalysisResult (not type-hinted here to avoid a
    circular import — igc.py imports this module's `recompute_site_coords`)."""

    def _add(site_id: str | None, kind: str, fix) -> None:
        if site_id is None:
            return
        db.add(
            SiteObservation(
                site_id=site_id,
                track_id=track.id,
                kind=kind,
                lat=fix.lat,
                lon=fix.lon,
                alt_m=fix.alt_m,
            )
        )

    _add(flight.launch_site_id, "takeoff", analysis.takeoff_fix)
    _add(flight.landing_site_id, "landing", analysis.landing_fix)


def clear_observations(db: Session, track_id: str) -> list[str]:
    """Delete this track's observations, returning the distinct site ids that need a
    recompute afterward (a replace/detach must not leave a stale fix skewing a median)."""
    rows = (
        db.execute(select(SiteObservation).where(SiteObservation.track_id == track_id))
        .scalars()
        .all()
    )
    site_ids = sorted({row.site_id for row in rows})
    for row in rows:
        db.delete(row)
    return site_ids


def recompute_site_coords(db: Session, site_id: str) -> None:
    """Recompute (or clear) a site's igc_median coordinates from its current observations.
    A no-op if the site was pinned by hand — that coordinate is never overwritten."""
    site = db.get(Site, site_id)
    if site is None or site.coord_source == "manual":
        return

    observations = (
        db.execute(select(SiteObservation).where(SiteObservation.site_id == site_id))
        .scalars()
        .all()
    )

    if len(observations) < MIN_OBSERVATIONS:
        if site.coord_source == "igc_median":
            # Dropped back below threshold (e.g. a detach) — clear the auto-set coordinate
            # rather than leave a stale median standing on fewer observations than the rule
            # requires.
            site.lat = None
            site.lon = None
            site.coord_source = None
            site.coord_accuracy_m = None
            logger.info("Site coord backfill cleared (below threshold): %s", site_id)
        return

    lats = [o.lat for o in observations]
    lons = [o.lon for o in observations]
    median_lat = statistics.median(lats)
    median_lon = statistics.median(lons)
    # Spread in meters — a simple median-absolute-deviation on latitude is enough for a
    # rough accuracy figure; 1 deg latitude is ~111_320 m everywhere.
    spread_deg = statistics.median([abs(lat - median_lat) for lat in lats]) if lats else 0.0
    accuracy_m = spread_deg * 111_320.0

    site.lat = median_lat
    site.lon = median_lon
    site.coord_source = "igc_median"
    site.coord_accuracy_m = accuracy_m
    logger.info(
        "Site coord backfill: %s -> (%.6f, %.6f) from %d observations, accuracy=%.1fm",
        site_id,
        median_lat,
        median_lon,
        len(observations),
        accuracy_m,
    )
