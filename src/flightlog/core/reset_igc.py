"""
One-shot IGC data reset.

    python -m flightlog.core.reset_igc              # dry-run (default) — reports counts only
    python -m flightlog.core.reset_igc --write       # commits, and deletes files on disk too

Clears every `igc_tracks` / `igc_segments` / `site_observations` row, plus any leftover
`igc_pending_uploads` row from the bulk-import feature removed in this same release (v0.8.1) —
a real bulk import mismatched flights and the pilot asked for both the feature and its bad data
gone. The `igc_pending_uploads` table itself is dropped: its model no longer exists in
`database/models.py`, so `Base.metadata.create_all()` will never touch it again on its own.

Also undoes the two side-effects those tracks wrote elsewhere, since both were derived from
data being deleted here:

- `flights.takeoff_time` / `landing_time` — the legacy workbook has no time-of-day anywhere
  (01-project-overview.md); every value in either column was backfilled from a track.
- Any site with `coord_source == "igc_median"` — that coordinate is the median of the
  `site_observations` rows this same pass deletes, so leaving it standing would strand a
  computed value with no basis. A `coord_source == "manual"` pin is never touched.

Not owner-scoped — a full reset, matching the ask; there is exactly one pilot account in this
system today, same assumption `core/importer.py` makes.
"""

from __future__ import annotations

import argparse
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from flightlog.database.models import Flight, IgcSegment, IgcTrack, Site, SiteObservation

logger = logging.getLogger(__name__)

_PENDING_TABLE = "igc_pending_uploads"


@dataclass
class ResetReport:
    tracks: int = 0
    segments: int = 0
    observations: int = 0
    pending_uploads: int = 0
    flights_with_times: int = 0
    sites_with_igc_median: int = 0


def _pending_table_exists(db: Session) -> bool:
    row = db.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": _PENDING_TABLE},
    ).scalar_one_or_none()
    return row is not None


def reset_igc_data(db: Session, write: bool = False) -> ResetReport:
    """Count (and, if `write`, delete/reset) every row left over from IGC tracks and the
    removed bulk-import feature. Never touches the filesystem — the caller deletes the
    on-disk `.igc` files separately, only once this commits."""
    report = ResetReport(
        tracks=len(db.execute(select(IgcTrack)).scalars().all()),
        segments=len(db.execute(select(IgcSegment)).scalars().all()),
        observations=len(db.execute(select(SiteObservation)).scalars().all()),
        pending_uploads=(
            db.execute(text(f"SELECT COUNT(*) FROM {_PENDING_TABLE}")).scalar_one()
            if _pending_table_exists(db)
            else 0
        ),
        flights_with_times=len(
            db.execute(
                select(Flight).where(
                    Flight.takeoff_time.is_not(None) | Flight.landing_time.is_not(None)
                )
            )
            .scalars()
            .all()
        ),
        sites_with_igc_median=len(
            db.execute(select(Site).where(Site.coord_source == "igc_median")).scalars().all()
        ),
    )

    if not write:
        return report

    db.execute(IgcSegment.__table__.delete())
    db.execute(SiteObservation.__table__.delete())
    if _pending_table_exists(db):
        db.execute(text(f"DROP TABLE {_PENDING_TABLE}"))
    db.execute(IgcTrack.__table__.delete())
    db.execute(update(Flight).values(takeoff_time=None, landing_time=None))
    db.execute(
        update(Site)
        .where(Site.coord_source == "igc_median")
        .values(lat=None, lon=None, coord_source=None, coord_accuracy_m=None)
    )
    db.commit()
    logger.info(
        "IGC data reset: %d tracks, %d segments, %d observations, %d pending uploads deleted; "
        "%d flights' times cleared; %d sites' igc_median coords cleared",
        report.tracks,
        report.segments,
        report.observations,
        report.pending_uploads,
        report.flights_with_times,
        report.sites_with_igc_median,
    )
    return report


def _delete_igc_files(igc_dir: str) -> int:
    """Removes every file under `igc_dir` and returns how many `.igc` files were deleted.
    Leaves the directory itself in place so the next real upload doesn't need to recreate it."""
    root = Path(igc_dir)
    if not root.exists():
        return 0
    count = sum(1 for p in root.rglob("*.igc"))
    for child in root.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    return count


def _print_report(report: ResetReport, write: bool, files_deleted: int | None) -> None:
    verb = "Deleted" if write else "Would delete"
    print(
        f"{verb} {report.tracks} igc_tracks, {report.segments} igc_segments, "
        f"{report.observations} site_observations, {report.pending_uploads} igc_pending_uploads"
    )
    verb2 = "Cleared" if write else "Would clear"
    print(f"{verb2} takeoff_time/landing_time on {report.flights_with_times} flight(s)")
    print(f"{verb2} igc_median coordinates on {report.sites_with_igc_median} site(s)")
    if write:
        print(f"Deleted {files_deleted} .igc file(s) from disk")
    else:
        print("Re-run with --write to apply, and delete the on-disk .igc files")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    from flightlog.config import load_config
    from flightlog.database.db import init_db

    cfg = load_config()
    engine = init_db(cfg.database.path)
    with Session(engine) as db:
        report = reset_igc_data(db, write=args.write)

    files_deleted = _delete_igc_files(cfg.storage.igc_dir) if args.write else None
    _print_report(report, args.write, files_deleted)


if __name__ == "__main__":
    main()
