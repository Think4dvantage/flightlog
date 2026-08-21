"""Admin re-analysis: reprocesses stale tracks, 403 for a non-admin pilot account."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

FIXTURES = Path(__file__).parent / "fixtures"
VALID = (FIXTURES / "valid_flight.igc").read_bytes()


@pytest.fixture
def flight_with_track(db_session, make_user):
    from flightlog.database.models import Flight, FlightCategory, Site

    user = make_user()
    launch = Site(owner_id=user.id, name="Launch", is_launch=True)
    category = FlightCategory(owner_id=user.id, name="Thermikflug", slug="thermikflug")
    db_session.add_all([launch, category])
    db_session.commit()

    flight = Flight(
        owner_id=user.id,
        flight_date=date(2024, 8, 15),
        launch_site_id=launch.id,
        category_id=category.id,
    )
    db_session.add(flight)
    db_session.commit()
    return user, flight


async def test_reanalyze_is_admin_only(client, make_token, make_user):
    pilot_headers = make_token(user=make_user(email="pilot@example.com"))
    resp = await client.post("/api/admin/reanalyze", headers=pilot_headers)
    assert resp.status_code == 403

    admin_headers = make_token(user=make_user(email="admin@example.com", role="admin"))
    resp2 = await client.post("/api/admin/reanalyze", headers=admin_headers)
    assert resp2.status_code == 200


async def test_reanalyze_reprocesses_stale_tracks(
    client, make_token, flight_with_track, db_session, make_user
):
    from flightlog.database.models import IgcTrack

    user, flight = flight_with_track
    headers = make_token(user=user)
    await client.post(
        f"/api/flights/{flight.id}/igc",
        files={"file": ("valid.igc", VALID, "application/octet-stream")},
        headers=headers,
    )

    track = db_session.execute(select(IgcTrack).where(IgcTrack.flight_id == flight.id)).scalar_one()
    track.analyzer_version = "0"  # simulate a stale track from before an algorithm change
    old_analyzed_at = track.analyzed_at
    db_session.commit()

    admin_headers = make_token(user=make_user(email="admin2@example.com", role="admin"))
    resp = await client.post("/api/admin/reanalyze", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["reanalyzed_count"] == 1

    db_session.refresh(track)
    assert track.analyzer_version == "2"
    assert track.analyzed_at != old_analyzed_at
