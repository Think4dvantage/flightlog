"""
IGC tracks.

    POST   /api/flights/{id}/igc            — upload; create-or-replace (FR-004)
    GET    /api/flights/{id}/igc            — summary
    DELETE /api/flights/{id}/igc            — detach
    GET    /api/flights/{id}/igc/segments
    GET    /api/flights/{id}/igc/track.geojson
    POST   /api/admin/reanalyze             — admin only, 403 for a pilot account

Every handler here is a plain sync `def`, matching every other router in this app — FastAPI
already runs sync path functions in its worker threadpool, so `core.igc.analyze()`'s CPU-bound
work never blocks the event loop without needing an explicit `asyncio.to_thread` call (that
matters when a handler is `async def`, which none of these are; see 04-constraints.md).

Bulk upload + the pending-review queue (`POST /api/igc/bulk`, `/api/igc/pending/*`) were removed
in v0.8.1 — a real bulk import mismatched flights and the pilot asked for it gone outright, not
just hidden. Per-flight upload above (unambiguous by construction) is the only attach path now.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user, require_admin
from flightlog.api.errors import AppException
from flightlog.config import get_config
from flightlog.core import igc as igc_core
from flightlog.core import igc_storage, site_backfill
from flightlog.core.flights import effective_elevation_m
from flightlog.database.db import get_db
from flightlog.database.models import (
    Flight,
    IgcSegment,
    IgcTrack,
    User,
    utcnow,
)
from flightlog.models.igc import (
    IgcSegmentOut,
    IgcTrackGeoJsonOut,
    IgcTrackGeoJsonPropertiesOut,
    IgcTrackGeometryOut,
    IgcTrackOut,
    ReanalyzeResultOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["igc"])


# ---- ownership helpers (one per router file, per 02-backend-conventions.md) ----


def _get_own_flight(flight_id: str, current_user: User, db: Session) -> Flight:
    row = db.get(Flight, flight_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Flight not found")
    return row


def _get_own_track(track_id: str, current_user: User, db: Session) -> IgcTrack:
    row = db.get(IgcTrack, track_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Track not found")
    return row


def _get_track_for_flight(flight: Flight, db: Session) -> IgcTrack:
    row = db.execute(select(IgcTrack).where(IgcTrack.flight_id == flight.id)).scalar_one_or_none()
    if row is None:
        raise AppException(404, "ENTITY_NOT_FOUND", "This flight has no track")
    return row


# ---- shared analysis/attach/backfill pipeline ----


def _store_and_analyze(current_user: User, filename: str, data: bytes) -> tuple[str, str, object]:
    """Write to content-addressed storage and analyze. Raises AppException(422, ...) for an
    oversized or invalid file — never a bare exception past this point."""
    cfg = get_config()
    try:
        sha256, file_path = igc_storage.write_igc(
            cfg.storage.igc_dir, current_user.id, data, cfg.storage.max_igc_bytes
        )
    except igc_storage.IgcTooLargeError as exc:
        raise AppException(
            422, "VALIDATION_FAILED", f"{filename}: file too large", {"error": str(exc)}
        ) from exc

    try:
        analysis = igc_core.analyze(file_path, cfg.igc.parsing)
    except igc_core.IgcInvalidError as exc:
        raise AppException(
            422, "VALIDATION_FAILED", f"{filename}: not a valid IGC file", {"notes": exc.notes}
        ) from exc

    return sha256, file_path, analysis


def _attach_track(
    db: Session,
    flight: Flight,
    current_user: User,
    filename: str,
    sha256: str,
    file_path: str,
    analysis,
) -> IgcTrack:
    """Create-or-replace `flight`'s track from an already-stored, already-analyzed file, then
    recompute site coordinate backfill. Caller commits."""
    existing = db.execute(
        select(IgcTrack).where(IgcTrack.flight_id == flight.id)
    ).scalar_one_or_none()
    if existing is not None and existing.sha256 == sha256:
        logger.info("IGC upload no-op (identical file already attached): flight=%s", flight.id)
        return existing

    # uq_igc_tracks_owner_sha256 is per-owner, not per-flight — the same physical
    # recording can only ever be attached to one flight at a time for this pilot. Without
    # this check the INSERT below hits that constraint as an unhandled IntegrityError,
    # which surfaces to the pilot as an opaque 500 instead of telling them where the file
    # already lives.
    conflict = db.execute(
        select(IgcTrack).where(IgcTrack.owner_id == current_user.id, IgcTrack.sha256 == sha256)
    ).scalar_one_or_none()
    if conflict is not None:
        raise AppException(
            409,
            "CONFLICT",
            f"{filename}: this IGC file is already attached to another flight",
            {"flight_id": conflict.flight_id},
        )

    affected_site_ids: set[str] = set()
    if existing is not None:
        affected_site_ids |= set(site_backfill.clear_observations(db, existing.id))
        db.delete(existing)
        db.flush()

    # architecture.md's "writeback shrinks the problem" — later bulk-match runs can use these
    # to match on time overlap, not just date+duration. Timing is untouched by altitude
    # calibration below, so this reads from the raw analysis either way.
    flight.takeoff_time = analysis.takeoff_fix.at
    flight.landing_time = analysis.landing_fix.at

    # Anchor absolute altitude to the launch site's known elevation (see
    # core/igc.py::calibrate_altitude()'s own docstring) — computed from the *raw* analysis,
    # before site_backfill.record_observations() below, which must keep seeing genuine raw
    # sensor readings. Feeding it a calibrated fix would make sites.elevation_igc_m a shifted
    # copy of the very elevation it's meant to be compared against.
    reference_elev_m = effective_elevation_m(
        db, current_user.id, flight.launch_site_id, flight.launch_elev_override_m
    )
    calibrated, offset_m = igc_core.calibrate_altitude(analysis, reference_elev_m)

    track = IgcTrack(
        owner_id=current_user.id,
        flight_id=flight.id,
        original_filename=filename,
        sha256=sha256,
        file_path=file_path,
        duration_s=calibrated.duration_s,
        distance_km=calibrated.distance_km,
        max_alt_igc_m=calibrated.max_alt_igc_m,
        alt_gain_igc_m=calibrated.alt_gain_igc_m,
        thermal_count=calibrated.thermal_count,
        best_climb_ms=calibrated.best_climb_ms,
        peak_climb_ms=calibrated.peak_climb_ms,
        glide_ratio=calibrated.glide_ratio,
        alt_source=calibrated.alt_source,
        alt_calibration_offset_m=offset_m,
        track_simplified_json=calibrated.track_simplified_json,
        analyzer_version=igc_core.ANALYZER_VERSION,
        analyzed_at=utcnow(),
    )
    db.add(track)
    db.flush()

    for seg in calibrated.segments:
        db.add(
            IgcSegment(
                track_id=track.id,
                kind=seg.kind,
                start_offset_s=seg.start_offset_s,
                start_at=seg.start_at,
                duration_s=seg.duration_s,
                alt_change_m=seg.alt_change_m,
                vertical_velocity_ms=seg.vertical_velocity_ms,
                glide_ratio=seg.glide_ratio,
            )
        )

    site_backfill.record_observations(db, track, flight, analysis)
    db.flush()
    affected_site_ids |= {sid for sid in (flight.launch_site_id, flight.landing_site_id) if sid}
    for site_id in affected_site_ids:
        site_backfill.recompute_site_coords(db, site_id)

    logger.info(
        "IGC track %s: flight=%s duration=%ds thermals=%d",
        "replaced" if existing is not None else "created",
        flight.id,
        analysis.duration_s,
        analysis.thermal_count,
    )
    return track


# ---- single-flight upload/view/detach ----


@router.post("/flights/{flight_id}/igc", response_model=IgcTrackOut)
def upload_igc(
    flight_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IgcTrackOut:
    flight = _get_own_flight(flight_id, current_user, db)
    filename = file.filename or "upload.igc"
    data = file.file.read()
    sha256, file_path, analysis = _store_and_analyze(current_user, filename, data)
    track = _attach_track(db, flight, current_user, filename, sha256, file_path, analysis)
    db.commit()
    db.refresh(track)
    return IgcTrackOut.model_validate(track)


@router.get("/flights/{flight_id}/igc", response_model=IgcTrackOut)
def get_igc(
    flight_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IgcTrackOut:
    flight = _get_own_flight(flight_id, current_user, db)
    track = _get_track_for_flight(flight, db)
    return IgcTrackOut.model_validate(track)


@router.delete("/flights/{flight_id}/igc", status_code=204)
def delete_igc(
    flight_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    flight = _get_own_flight(flight_id, current_user, db)
    track = _get_track_for_flight(flight, db)
    site_ids = site_backfill.clear_observations(db, track.id)
    flight.takeoff_time = None
    flight.landing_time = None
    db.delete(track)
    db.flush()
    for site_id in site_ids:
        site_backfill.recompute_site_coords(db, site_id)
    db.commit()
    logger.info("IGC track detached: flight=%s by %s", flight_id, current_user.id)


@router.get("/flights/{flight_id}/igc/segments", response_model=list[IgcSegmentOut])
def get_igc_segments(
    flight_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IgcSegmentOut]:
    flight = _get_own_flight(flight_id, current_user, db)
    track = _get_track_for_flight(flight, db)
    rows = (
        db.execute(
            select(IgcSegment)
            .where(IgcSegment.track_id == track.id)
            .order_by(IgcSegment.start_offset_s)
        )
        .scalars()
        .all()
    )
    return [IgcSegmentOut.model_validate(row) for row in rows]


@router.get("/flights/{flight_id}/igc/track.geojson", response_model=IgcTrackGeoJsonOut)
def get_igc_geojson(
    flight_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IgcTrackGeoJsonOut:
    flight = _get_own_flight(flight_id, current_user, db)
    track = _get_track_for_flight(flight, db)
    coordinates, offsets_s = igc_core.parse_simplified_track(track.track_simplified_json)
    return IgcTrackGeoJsonOut(
        geometry=IgcTrackGeometryOut(coordinates=coordinates),
        properties=IgcTrackGeoJsonPropertiesOut(offsets_s=offsets_s),
    )


# ---- admin re-analysis ----


@router.post("/admin/reanalyze", response_model=ReanalyzeResultOut)
def reanalyze(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ReanalyzeResultOut:
    cfg = get_config()
    stale = (
        db.execute(select(IgcTrack).where(IgcTrack.analyzer_version != igc_core.ANALYZER_VERSION))
        .scalars()
        .all()
    )

    count = 0
    for track in stale:
        try:
            analysis = igc_core.analyze(track.file_path, cfg.igc.parsing)
        except igc_core.IgcInvalidError as exc:
            logger.error("Re-analysis failed for track %s: %s", track.id, exc.notes)
            continue

        # No site_backfill.record_observations() call in this sweep at all, unlike upload —
        # so, unlike there, no raw-vs-calibrated split is needed here; calibrating in place
        # is safe.
        flight = db.get(Flight, track.flight_id)
        reference_elev_m = (
            effective_elevation_m(
                db, track.owner_id, flight.launch_site_id, flight.launch_elev_override_m
            )
            if flight is not None
            else None
        )
        calibrated, offset_m = igc_core.calibrate_altitude(analysis, reference_elev_m)

        db.execute(IgcSegment.__table__.delete().where(IgcSegment.track_id == track.id))
        for seg in calibrated.segments:
            db.add(
                IgcSegment(
                    track_id=track.id,
                    kind=seg.kind,
                    start_offset_s=seg.start_offset_s,
                    start_at=seg.start_at,
                    duration_s=seg.duration_s,
                    alt_change_m=seg.alt_change_m,
                    vertical_velocity_ms=seg.vertical_velocity_ms,
                    glide_ratio=seg.glide_ratio,
                )
            )

        track.duration_s = calibrated.duration_s
        track.distance_km = calibrated.distance_km
        track.max_alt_igc_m = calibrated.max_alt_igc_m
        track.alt_gain_igc_m = calibrated.alt_gain_igc_m
        track.thermal_count = calibrated.thermal_count
        track.best_climb_ms = calibrated.best_climb_ms
        track.peak_climb_ms = calibrated.peak_climb_ms
        track.glide_ratio = calibrated.glide_ratio
        track.alt_source = calibrated.alt_source
        track.alt_calibration_offset_m = offset_m
        track.track_simplified_json = calibrated.track_simplified_json
        track.analyzer_version = igc_core.ANALYZER_VERSION
        track.analyzed_at = utcnow()
        count += 1

    db.commit()
    logger.info("Re-analysis sweep: %d/%d tracks reprocessed", count, len(stale))
    return ReanalyzeResultOut(reanalyzed_count=count)
