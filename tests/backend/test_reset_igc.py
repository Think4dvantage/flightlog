"""IGC data reset: dry-run counts only, --write clears tracks/segments/observations/pending
uploads and undoes their two side-effects (flight times, igc_median site coords)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import text

from flightlog.core.reset_igc import reset_igc_data
from flightlog.database.models import Flight, FlightCategory, Site

FIXTURES = Path(__file__).parent / "fixtures"
VALID = (FIXTURES / "valid_flight.igc").read_bytes()


async def _seed_track(client, make_token, make_user, db_session):
    """A real flight with an attached track, via the same path the pilot uses — creates an
    igc_track, its segments, and two site_observations (launch + landing)."""
    user = make_user()
    launch = Site(owner_id=user.id, name="Launch", is_launch=True)
    landing = Site(owner_id=user.id, name="Landing", is_landing=True)
    category = FlightCategory(owner_id=user.id, name="Thermikflug", slug="thermikflug")
    db_session.add_all([launch, landing, category])
    db_session.commit()

    flight = Flight(
        owner_id=user.id,
        flight_date=date(2024, 8, 15),
        launch_site_id=launch.id,
        landing_site_id=landing.id,
        category_id=category.id,
    )
    db_session.add(flight)
    db_session.commit()

    headers = make_token(user=user)
    resp = await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("valid.igc", VALID, "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 200

    # Simulate a coordinate the (now-removed) bulk backfill would have set on the launch site.
    launch.coord_source = "igc_median"
    launch.lat = 46.5
    launch.lon = 7.9
    launch.coord_accuracy_m = 12.0
    db_session.commit()

    return user, flight, launch


async def test_dry_run_reports_but_deletes_nothing(client, make_token, make_user, db_session):
    _, flight, launch = await _seed_track(client, make_token, make_user, db_session)

    report = reset_igc_data(db_session, write=False)
    assert report.tracks == 1
    assert report.segments >= 1
    assert report.observations == 2
    assert report.flights_with_times == 1
    assert report.sites_with_igc_median == 1

    db_session.refresh(flight)
    db_session.refresh(launch)
    assert flight.takeoff_time is not None
    assert launch.coord_source == "igc_median"
    assert len(db_session.execute(text("SELECT 1 FROM igc_tracks")).all()) == 1


async def test_write_clears_tracks_and_their_two_side_effects(
    client, make_token, make_user, db_session
):
    _, flight, launch = await _seed_track(client, make_token, make_user, db_session)

    report = reset_igc_data(db_session, write=True)
    assert report.tracks == 1

    assert db_session.execute(text("SELECT 1 FROM igc_tracks")).all() == []
    assert db_session.execute(text("SELECT 1 FROM igc_segments")).all() == []
    assert db_session.execute(text("SELECT 1 FROM site_observations")).all() == []

    db_session.refresh(flight)
    db_session.refresh(launch)
    assert flight.takeoff_time is None
    assert flight.landing_time is None
    assert launch.coord_source is None
    assert launch.lat is None
    assert launch.lon is None
    assert launch.coord_accuracy_m is None


def test_write_drops_a_leftover_pending_uploads_table(db_session):
    # Simulates upgrading from a pre-v0.8.1 database where the (now-removed) bulk-import
    # feature left a row behind — the model is gone, so this is raw SQL, not the ORM.
    db_session.execute(
        text(
            "CREATE TABLE igc_pending_uploads ("
            "id TEXT PRIMARY KEY, owner_id TEXT, sha256 TEXT, file_path TEXT, "
            "original_filename TEXT, status TEXT, reason TEXT, "
            "candidate_flight_ids_json TEXT, resolved_flight_id TEXT, "
            "created_at TEXT, resolved_at TEXT)"
        )
    )
    db_session.execute(
        text(
            "INSERT INTO igc_pending_uploads "
            "(id, owner_id, sha256, file_path, original_filename, status) "
            "VALUES ('p1', 'u1', 'sha', '/tmp/x.igc', 'x.igc', 'rejected')"
        )
    )
    db_session.commit()

    report = reset_igc_data(db_session, write=False)
    assert report.pending_uploads == 1

    reset_igc_data(db_session, write=True)
    exists = db_session.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='igc_pending_uploads'")
    ).scalar_one_or_none()
    assert exists is None
