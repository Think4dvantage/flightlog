"""
IGC tracks.

    POST   /api/flights/{id}/igc            — upload; create-or-replace (FR-004)
    GET    /api/flights/{id}/igc            — summary
    DELETE /api/flights/{id}/igc            — detach
    GET    /api/flights/{id}/igc/segments
    GET    /api/flights/{id}/igc/track.geojson
    POST   /api/igc/bulk                    — multipart, multiple files
    GET    /api/igc/pending
    POST   /api/igc/pending/{id}/resolve
    DELETE /api/igc/pending/{id}
    POST   /api/admin/reanalyze             — admin only, 403 for a pilot account

Every handler here is a plain sync `def`, matching every other router in this app — FastAPI
already runs sync path functions in its worker threadpool, so `core.igc.analyze()`'s CPU-bound
work never blocks the event loop without needing an explicit `asyncio.to_thread` call (that
matters when a handler is `async def`, which none of these are; see 04-constraints.md).
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from flightlog.api.dependencies import get_current_user, require_admin
from flightlog.api.errors import AppException
from flightlog.config import get_config
from flightlog.core import igc as igc_core
from flightlog.core import igc_storage, site_backfill
from flightlog.database.db import get_db
from flightlog.database.models import (
    Flight,
    IgcPendingUpload,
    IgcSegment,
    IgcTrack,
    User,
    utcnow,
)
from flightlog.models.igc import (
    BulkUploadOutcomeOut,
    IgcPendingResolveIn,
    IgcPendingUploadOut,
    IgcSegmentOut,
    IgcTrackGeoJsonOut,
    IgcTrackGeoJsonPropertiesOut,
    IgcTrackGeometryOut,
    IgcTrackOut,
    ReanalyzeResultOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["igc"])

# Auto-attach only when the best-matching flight's duration is this close to the track's
# measured duration, and the runner-up candidate is well clear of it (architecture.md's
# bulk-match algorithm) — never guessed when two flights are plausible.
AUTO_MATCH_MAX_DELTA_S = 3 * 60
AUTO_MATCH_RUNNER_UP_MIN_GAP_S = 10 * 60


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


def _get_own_pending(pending_id: str, current_user: User, db: Session) -> IgcPendingUpload:
    row = db.get(IgcPendingUpload, pending_id)
    if row is None or row.owner_id != current_user.id:
        raise AppException(404, "ENTITY_NOT_FOUND", "Pending upload not found")
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

    affected_site_ids: set[str] = set()
    if existing is not None:
        affected_site_ids |= set(site_backfill.clear_observations(db, existing.id))
        db.delete(existing)
        db.flush()

    # architecture.md's "writeback shrinks the problem" — later bulk-match runs can use these
    # to match on time overlap, not just date+duration.
    flight.takeoff_time = analysis.takeoff_fix.at
    flight.landing_time = analysis.landing_fix.at

    track = IgcTrack(
        owner_id=current_user.id,
        flight_id=flight.id,
        original_filename=filename,
        sha256=sha256,
        file_path=file_path,
        duration_s=analysis.duration_s,
        distance_km=analysis.distance_km,
        max_alt_igc_m=analysis.max_alt_igc_m,
        alt_gain_igc_m=analysis.alt_gain_igc_m,
        thermal_count=analysis.thermal_count,
        best_climb_ms=analysis.best_climb_ms,
        peak_climb_ms=analysis.peak_climb_ms,
        glide_ratio=analysis.glide_ratio,
        alt_source=analysis.alt_source,
        track_simplified_json=analysis.track_simplified_json,
        analyzer_version=igc_core.ANALYZER_VERSION,
        analyzed_at=utcnow(),
    )
    db.add(track)
    db.flush()

    for seg in analysis.segments:
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
    points = json.loads(track.track_simplified_json or "[]")
    coordinates = [[lon, lat, alt] for _offset, lat, lon, alt in points]
    offsets_s = [offset for offset, _lat, _lon, _alt in points]
    return IgcTrackGeoJsonOut(
        geometry=IgcTrackGeometryOut(coordinates=coordinates),
        properties=IgcTrackGeoJsonPropertiesOut(offsets_s=offsets_s),
    )


# ---- bulk upload + pending review ----


def _find_bulk_match(db: Session, current_user: User, flight_date, duration_s: int) -> dict:
    """architecture.md's bulk-match algorithm. Scores every untracked same-day flight by how
    close its logged duration is to the track's measured one; auto-attaches only when the
    best match is close AND clearly better than the next-best candidate. Reads the full
    parsed analysis rather than architecture.md's original "header-only date" fast path —
    the file needs a full parse regardless once it's going to be attached or held pending, so
    a separate lightweight pre-scan would just be a second parsing path for no real saving
    (research.md accepts a bulk batch being slower as a documented tradeoff already)."""
    candidates = (
        db.execute(
            select(Flight).where(
                Flight.owner_id == current_user.id,
                Flight.flight_date == flight_date,
            )
        )
        .scalars()
        .all()
    )
    candidates = [f for f in candidates if f.igc_track is None]
    if not candidates:
        return {"outcome": "needs_resolution", "candidates": []}

    scored = sorted(
        ((abs((f.duration_min or 0) * 60 - duration_s), f) for f in candidates),
        key=lambda pair: pair[0],
    )
    best_delta, best_flight = scored[0]
    runner_up_delta = scored[1][0] if len(scored) > 1 else None

    if best_delta <= AUTO_MATCH_MAX_DELTA_S and (
        runner_up_delta is None or runner_up_delta - best_delta >= AUTO_MATCH_RUNNER_UP_MIN_GAP_S
    ):
        return {"outcome": "auto_attached", "flight": best_flight}
    return {"outcome": "needs_resolution", "candidates": [f.id for f in candidates]}


@router.post("/igc/bulk", response_model=list[BulkUploadOutcomeOut])
def bulk_upload_igc(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BulkUploadOutcomeOut]:
    results: list[BulkUploadOutcomeOut] = []
    for file in files:
        filename = file.filename or "upload.igc"
        data = file.file.read()
        try:
            sha256, file_path, analysis = _store_and_analyze(current_user, filename, data)
        except AppException as exc:
            results.append(
                BulkUploadOutcomeOut(filename=filename, outcome="rejected", reason=exc.message)
            )
            continue

        existing_pending = db.execute(
            select(IgcPendingUpload).where(
                IgcPendingUpload.owner_id == current_user.id,
                IgcPendingUpload.sha256 == sha256,
            )
        ).scalar_one_or_none()
        # Only an *unresolved* pending row blocks reprocessing — a dismissed or already-
        # resolved one must not, or a dismissed file could never be reconsidered (its
        # UniqueConstraint("owner_id", "sha256") slot is reused below instead of violated).
        if existing_pending is not None and existing_pending.resolved_at is None:
            results.append(
                BulkUploadOutcomeOut(
                    filename=filename,
                    outcome="needs_resolution",
                    pending_id=existing_pending.id,
                    candidate_flight_ids=(
                        json.loads(existing_pending.candidate_flight_ids_json)
                        if existing_pending.candidate_flight_ids_json
                        else None
                    ),
                    reason="Already uploaded and still awaiting resolution",
                )
            )
            continue

        match = _find_bulk_match(
            db, current_user, analysis.takeoff_fix.at.date(), analysis.duration_s
        )
        if match["outcome"] == "auto_attached":
            flight = match["flight"]
            _attach_track(db, flight, current_user, filename, sha256, file_path, analysis)
            db.commit()
            results.append(
                BulkUploadOutcomeOut(
                    filename=filename, outcome="auto_attached", flight_id=flight.id
                )
            )
            continue

        candidates = match["candidates"]
        status = "needs_resolution" if candidates else "rejected"
        reason = None if candidates else f"No flight logged on {analysis.takeoff_fix.at.date()}"
        candidate_json = json.dumps(candidates) if candidates else None

        if existing_pending is not None:
            # A previously dismissed/resolved row for this exact file — reuse it rather than
            # insert a second row and violate UniqueConstraint("owner_id", "sha256").
            pending = existing_pending
            pending.file_path = file_path
            pending.original_filename = filename
            pending.status = status
            pending.reason = reason
            pending.candidate_flight_ids_json = candidate_json
            pending.resolved_flight_id = None
            pending.resolved_at = None
        else:
            pending = IgcPendingUpload(
                owner_id=current_user.id,
                sha256=sha256,
                file_path=file_path,
                original_filename=filename,
                status=status,
                reason=reason,
                candidate_flight_ids_json=candidate_json,
            )
            db.add(pending)
        db.commit()
        results.append(
            BulkUploadOutcomeOut(
                filename=filename,
                outcome="needs_resolution" if candidates else "rejected",
                candidate_flight_ids=candidates or None,
                pending_id=pending.id,
                reason=pending.reason,
            )
        )

    logger.info(
        "Bulk IGC upload: %d files, %d auto-attached, %d needing resolution/rejected by %s",
        len(files),
        sum(1 for r in results if r.outcome == "auto_attached"),
        sum(1 for r in results if r.outcome != "auto_attached"),
        current_user.id,
    )
    return results


@router.get("/igc/pending", response_model=list[IgcPendingUploadOut])
def list_pending(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IgcPendingUploadOut]:
    rows = (
        db.execute(
            select(IgcPendingUpload)
            .where(
                IgcPendingUpload.owner_id == current_user.id, IgcPendingUpload.resolved_at.is_(None)
            )
            .order_by(IgcPendingUpload.created_at)
        )
        .scalars()
        .all()
    )
    return [
        IgcPendingUploadOut(
            id=row.id,
            original_filename=row.original_filename,
            status=row.status,
            reason=row.reason,
            candidate_flight_ids=(
                json.loads(row.candidate_flight_ids_json) if row.candidate_flight_ids_json else None
            ),
            created_at=row.created_at,
            resolved_at=row.resolved_at,
        )
        for row in rows
    ]


@router.post("/igc/pending/{pending_id}/resolve", response_model=IgcTrackOut)
def resolve_pending(
    pending_id: str,
    body: IgcPendingResolveIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IgcTrackOut:
    pending = _get_own_pending(pending_id, current_user, db)
    flight = _get_own_flight(body.flight_id, current_user, db)

    data = igc_storage.read_igc(pending.file_path)
    _sha256, file_path, analysis = _store_and_analyze(current_user, pending.original_filename, data)
    track = _attach_track(
        db, flight, current_user, pending.original_filename, pending.sha256, file_path, analysis
    )
    pending.resolved_flight_id = flight.id
    pending.resolved_at = utcnow()
    db.commit()
    db.refresh(track)
    logger.info("Pending IGC upload resolved: %s -> flight %s", pending_id, flight.id)
    return IgcTrackOut.model_validate(track)


@router.delete("/igc/pending/{pending_id}", status_code=204)
def dismiss_pending(
    pending_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    pending = _get_own_pending(pending_id, current_user, db)
    pending.resolved_at = utcnow()
    db.commit()
    logger.info("Pending IGC upload dismissed: %s by %s", pending_id, current_user.id)


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

        db.execute(IgcSegment.__table__.delete().where(IgcSegment.track_id == track.id))
        for seg in analysis.segments:
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

        track.duration_s = analysis.duration_s
        track.distance_km = analysis.distance_km
        track.max_alt_igc_m = analysis.max_alt_igc_m
        track.alt_gain_igc_m = analysis.alt_gain_igc_m
        track.thermal_count = analysis.thermal_count
        track.best_climb_ms = analysis.best_climb_ms
        track.peak_climb_ms = analysis.peak_climb_ms
        track.glide_ratio = analysis.glide_ratio
        track.alt_source = analysis.alt_source
        track.track_simplified_json = analysis.track_simplified_json
        track.analyzer_version = igc_core.ANALYZER_VERSION
        track.analyzed_at = utcnow()
        count += 1

    db.commit()
    logger.info("Re-analysis sweep: %d/%d tracks reprocessed", count, len(stale))
    return ReanalyzeResultOut(reanalyzed_count=count)
